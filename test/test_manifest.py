"""Offline regressions for optional DRM metadata and both manifest layouts."""

import asyncio
import base64
import unittest
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import patch

import xmltodict

from crunpyroll.methods.get_manifest import GetManifest
from crunpyroll.types import ContentProtection, DRM, Manifest
from crunpyroll.utils import PLAYREADY_UUID, WIDEVINE_UUID


KEY_ID = "00112233-4455-6677-8899-aabbccddeeff"
# A version 1 PSSH box with one KID and no system-specific data.
PSSH = base64.b64encode(
    (52).to_bytes(4, "big")
    + b"pssh\x01\x00\x00\x00"
    + UUID(WIDEVINE_UUID.rsplit(":", 1)[1]).bytes
    + (1).to_bytes(4, "big")
    + UUID(KEY_ID).bytes
    + (0).to_bytes(4, "big")
).decode("ascii")
PLAYREADY_PSSH = "cGxheXJlYWR5"


def make_manifest(systems=(), mime_location="representation", default_kid=True):
    protection = ""
    if "widevine" in systems:
        kid = ' cenc:default_KID="{}"'.format(KEY_ID) if default_kid else ""
        protection += (
            '<ContentProtection schemeIdUri="{}"{}>'
            '<cenc:pssh>{}</cenc:pssh></ContentProtection>'
        ).format(WIDEVINE_UUID, kid, PSSH)
    if "playready" in systems:
        protection += (
            '<ContentProtection schemeIdUri="{}">'
            '<mspr:pro>{}</mspr:pro></ContentProtection>'
        ).format(PLAYREADY_UUID, PLAYREADY_PSSH)
    adaptations = []
    for kind, codecs, bandwidth in (
        ("video", "avc1.640028", 5000000),
        ("audio", "mp4a.40.2", 128000),
    ):
        mime = ' mimeType="{}/mp4"'.format(kind)
        adaptations.append(
            '<AdaptationSet{adaptation_mime}>{protection}'
            '<SegmentTemplate startNumber="1" initialization="init-$RepresentationID$.mp4"'
            ' media="chunk-$Number$.m4s">'
            '<SegmentTimeline><S d="2000" r="1"/></SegmentTimeline>'
            '</SegmentTemplate>'
            '<Representation id="{kind}"{representation_mime} codecs="{codecs}"'
            ' width="1920" height="1080" bandwidth="{bandwidth}">'
            '<BaseURL>https://example.invalid/{kind}/</BaseURL>'
            '</Representation></AdaptationSet>'.format(
                adaptation_mime=mime if mime_location == "adaptation" else "",
                representation_mime=mime if mime_location == "representation" else "",
                protection=protection,
                kind=kind,
                codecs=codecs,
                bandwidth=bandwidth,
            )
        )
    return (
        '<MPD xmlns:cenc="urn:mpeg:cenc:2013" xmlns:mspr="urn:microsoft:playready">'
        '<Period>{}</Period></MPD>'
    ).format("".join(adaptations))


def make_segment_base_manifest(systems=("widevine", "playready")):
    """Match the first episode's layout using synthetic metadata and URLs."""
    document = xmltodict.parse(make_manifest(systems, "adaptation", default_kid=False))
    for aset in document["MPD"]["Period"]["AdaptationSet"]:
        aset.pop("SegmentTemplate")
        protection = aset.get("ContentProtection", [])
        if isinstance(protection, dict):
            protection = [protection]
        if systems:
            protection.insert(0, {
                "@schemeIdUri": "urn:mpeg:dash:mp4protection:2011",
                "@xmlns:cenc": "urn:mpeg:cenc:2013",
                "@cenc:default_KID": KEY_ID,
                "@value": "cenc",
            })
            for drm in protection:
                for name, namespace in (
                    ("cenc:pssh", "urn:mpeg:cenc:2013"),
                    ("mspr:pro", "urn:microsoft:playready"),
                ):
                    if name in drm:
                        drm[name] = {
                            "@xmlns:" + name.split(":")[0]: namespace,
                            "#text": drm[name],
                        }
            aset["ContentProtection"] = protection
        representation = aset["Representation"]
        representation["BaseURL"] += "full.mp4?token=fixture"
        representation["SegmentBase"] = {
            "@indexRange": "100-199", "Initialization": {"@range": "0-99"}
        }
    return xmltodict.unparse(document)


class TestDRM(unittest.TestCase):
    def test_missing_drm_fields(self):
        for data in (None, {}):
            with self.subTest(data=data):
                drm = DRM(data)
                self.assertIsNone(drm.key_id)
                self.assertIsNone(drm.pssh)

    def test_missing_content_protection(self):
        for data in (None, {}, {"widevine": None, "playready": None}):
            with self.subTest(data=data):
                protection = ContentProtection(data)
                for drm in (protection.widevine, protection.playready):
                    self.assertIsInstance(drm, DRM)
                    self.assertIsNone(drm.key_id)
                    self.assertIsNone(drm.pssh)

    def test_present_fields_are_preserved(self):
        protection = ContentProtection({"widevine": {"key_id": KEY_ID, "pssh": PSSH}})
        self.assertEqual(protection.widevine.key_id, KEY_ID)
        self.assertEqual(protection.widevine.pssh, PSSH)
        self.assertIsNone(protection.playready.pssh)

    def test_manifest_without_protection_metadata(self):
        for data in ({}, {"content_protection": None}):
            with self.subTest(data=data):
                manifest = Manifest(data)
                self.assertIsNone(manifest.content_protection.widevine.pssh)
                self.assertIsNone(manifest.content_protection.playready.pssh)


class TestManifest(unittest.TestCase):
    def assert_streams(self, manifest):
        self.assertEqual(len(manifest.video_streams), 1)
        self.assertEqual(len(manifest.audio_streams), 1)
        self.assertEqual(manifest.video_streams[0].height, 1080)
        self.assertEqual(manifest.audio_streams[0].bitrate, 128000)
        for kind, streams in (
            ("video", manifest.video_streams), ("audio", manifest.audio_streams)
        ):
            self.assertEqual(streams[0].segments, [
                "https://example.invalid/{}/init-{}.mp4".format(kind, kind),
                "https://example.invalid/{}/chunk-1.m4s".format(kind),
                "https://example.invalid/{}/chunk-2.m4s".format(kind),
            ])

    def test_optional_drm_in_both_parsers_and_mime_layouts(self):
        for parser in (Manifest.parse, Manifest.new_parse):
            for systems in ((), ("widevine",), ("playready",), ("widevine", "playready")):
                for mime_location in ("representation", "adaptation"):
                    with self.subTest(
                        parser=parser.__name__, systems=systems, mime=mime_location
                    ):
                        xml = make_manifest(systems, mime_location)
                        manifest = parser(xml)
                        self.assert_streams(manifest)
                        self.assertEqual(manifest.plain, xml)
                        protection = manifest.content_protection
                        self.assertEqual(
                            protection.widevine.pssh,
                            PSSH if "widevine" in systems else None,
                        )
                        self.assertEqual(
                            protection.playready.pssh,
                            PLAYREADY_PSSH if "playready" in systems else None,
                        )
                        if "widevine" in systems:
                            self.assertEqual(str(protection.widevine.key_id), KEY_ID)
                        else:
                            self.assertIsNone(protection.widevine.key_id)

    def test_representation_mime_overrides_adaptation_mime(self):
        xml = make_manifest().replace(
            "<AdaptationSet>", '<AdaptationSet mimeType="application/mp4">'
        )
        for parser in (Manifest.parse, Manifest.new_parse):
            with self.subTest(parser=parser.__name__):
                self.assert_streams(parser(xml))

    def test_public_get_manifest_without_drm_does_not_need_fallback(self):
        for mime_location in ("representation", "adaptation"):
            with self.subTest(mime=mime_location):
                xml = make_manifest(mime_location=mime_location)
                with patch.object(
                    Manifest, "new_parse", side_effect=AssertionError("Unexpected fallback")
                ):
                    manifest = asyncio.run(fetch_manifest(xml))
                self.assert_streams(manifest)

    def test_public_get_manifest_without_default_kid(self):
        for mime_location in ("representation", "adaptation"):
            with self.subTest(mime=mime_location):
                xml = make_manifest(("widevine",), mime_location, default_kid=False)
                manifest = asyncio.run(fetch_manifest(xml))
                self.assert_streams(manifest)
                self.assertEqual(str(manifest.content_protection.widevine.key_id), KEY_ID)
                self.assertEqual(manifest.content_protection.widevine.pssh, PSSH)
                self.assertIsNone(manifest.content_protection.playready.pssh)

    def test_segment_base_with_namespaced_drm_and_common_kid(self):
        xml = make_segment_base_manifest()
        for parser in (Manifest.parse, Manifest.new_parse):
            with self.subTest(parser=parser.__name__):
                manifest = parser(xml)
                self.assertEqual(len(manifest.video_streams), 1)
                self.assertEqual(len(manifest.audio_streams), 1)
                for kind, streams in (
                    ("video", manifest.video_streams),
                    ("audio", manifest.audio_streams),
                ):
                    self.assertEqual(streams[0].segments, [
                        "https://example.invalid/{}/full.mp4?token=fixture".format(kind)
                    ])
                self.assertEqual(manifest.content_protection.widevine.key_id, KEY_ID)
                self.assertEqual(manifest.content_protection.widevine.pssh, PSSH)
                self.assertEqual(manifest.content_protection.playready.pssh, PLAYREADY_PSSH)

    def test_public_get_manifest_segment_base_with_optional_drm(self):
        for systems in ((), ("widevine",), ("playready",), ("widevine", "playready")):
            with self.subTest(systems=systems):
                manifest = asyncio.run(fetch_manifest(make_segment_base_manifest(systems)))
                self.assertEqual(len(manifest.video_streams), 1)
                self.assertEqual(len(manifest.audio_streams), 1)
                self.assertEqual(len(manifest.video_streams[0].segments), 1)
                self.assertEqual(len(manifest.audio_streams[0].segments), 1)
                self.assertEqual(bool(manifest.content_protection.widevine.pssh), "widevine" in systems)
                self.assertEqual(bool(manifest.content_protection.playready.pssh), "playready" in systems)

    def test_representation_segment_template(self):
        document = xmltodict.parse(make_manifest(("widevine",), "adaptation"))
        for aset in document["MPD"]["Period"]["AdaptationSet"]:
            aset["Representation"]["SegmentTemplate"] = aset.pop("SegmentTemplate")
        xml = xmltodict.unparse(document)
        for parser in (Manifest.parse, Manifest.new_parse):
            with self.subTest(parser=parser.__name__):
                manifest = parser(xml)
                self.assert_streams(manifest)
                self.assertEqual(manifest.content_protection.widevine.pssh, PSSH)

    def test_segment_base_missing_url_is_an_explicit_error(self):
        document = xmltodict.parse(make_segment_base_manifest())
        document["MPD"]["Period"]["AdaptationSet"][0]["Representation"].pop("BaseURL")
        with self.assertRaisesRegex(ValueError, "SegmentBase representation is missing BaseURL"):
            Manifest.parse(xmltodict.unparse(document))

    def test_widevine_protobuf_kid_without_default_kid(self):
        payload = b"\x08\x01\x12\x10" + UUID(KEY_ID).bytes
        pssh = base64.b64encode(
            (32 + len(payload)).to_bytes(4, "big")
            + b"pssh\x00\x00\x00\x00"
            + UUID(WIDEVINE_UUID.rsplit(":", 1)[1]).bytes
            + len(payload).to_bytes(4, "big")
            + payload
        ).decode("ascii")
        xml = make_manifest(("widevine",), default_kid=False).replace(PSSH, pssh)
        manifest = asyncio.run(fetch_manifest(xml))
        self.assert_streams(manifest)
        self.assertEqual(manifest.content_protection.widevine.key_id, KEY_ID)

    def test_invalid_pssh_does_not_discard_streams(self):
        xml = make_manifest(("widevine",), default_kid=False).replace(PSSH, "invalid")
        manifest = asyncio.run(fetch_manifest(xml))
        self.assert_streams(manifest)
        self.assertIsNone(manifest.content_protection.widevine.key_id)

    def test_malformed_template_representation_does_not_discard_valid_streams(self):
        document = xmltodict.parse(make_manifest())
        aset = document["MPD"]["Period"]["AdaptationSet"][0]
        valid = aset["Representation"]
        invalid = dict(valid)
        invalid.pop("@codecs")
        aset["Representation"] = [invalid, valid]
        manifest = asyncio.run(fetch_manifest(xmltodict.unparse(document)))
        self.assert_streams(manifest)

    def test_incomplete_audio_drm_preserves_video_drm(self):
        document = xmltodict.parse(make_segment_base_manifest())
        audio = document["MPD"]["Period"]["AdaptationSet"][1]
        audio["ContentProtection"] = [
            {"@schemeIdUri": WIDEVINE_UUID}, {"@schemeIdUri": PLAYREADY_UUID}
        ]
        manifest = asyncio.run(fetch_manifest(xmltodict.unparse(document)))
        self.assertEqual(manifest.content_protection.widevine.pssh, PSSH)
        self.assertEqual(manifest.content_protection.widevine.key_id, KEY_ID)
        self.assertEqual(manifest.content_protection.playready.pssh, PLAYREADY_PSSH)


async def fetch_manifest(xml):
    async def retrieve():
        pass

    async def manifest_request(url):
        return xml

    client = SimpleNamespace(
        session=SimpleNamespace(retrieve=retrieve), manifest_request=manifest_request
    )
    return await GetManifest.get_manifest(client, "https://example.invalid/manifest.mpd")


if __name__ == "__main__":
    unittest.main()
