import base64
from uuid import UUID

from .obj import Object
from .drm import ContentProtection
from crunpyroll.types import SubtitlesStream
from ..utils import (
    WIDEVINE_UUID,
    PLAYREADY_UUID,
    parse_segments
)

from typing import List, Dict, Any, Optional

import xmltodict


def _as_list(x: Any) -> list:
    """Normalize xmltodict single element (dict) or multiple (list) to a list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _xml_text(value: Any) -> Optional[str]:
    """Elements with namespace declarations have their value in #text."""
    return value.get("#text") if isinstance(value, dict) else value


def _safe_stream_parse(cls: type, repr: Dict, template: Dict) -> Any:
    """单条 Representation 解析失败时跳过，不让个别坏数据崩掉整个 manifest。"""
    try:
        return cls.parse(repr, template)
    except Exception:
        return None

def _widevine_key_id_from_pssh(pssh_b64: str) -> str | None:
    """从 widevine pssh box 中尽力解码 KID。

    box data（偏移 32 起）的常见形态：裸 16 字节 KID（shaka 等
    打包器），或 protobuf SignedMessage（08 01 12 10 <KID>，可能还
    带前置 version 字段）。以 \x12\x10（field 2, 长度 16）为锚点
    定位 KID，找不到再按裸 KID 兜底。"""
    try:
        decoded = base64.b64decode(pssh_b64)
        data = decoded[32:]
        idx = data.find(b"\x12\x10")
        if idx != -1 and idx + 18 <= len(data):
            return str(UUID(bytes=data[idx + 2:idx + 18]))
        if len(data) >= 16:
            return str(UUID(bytes=data[:16]))
    except Exception:
        return None
    return None


def _parse_content_protection(elements: Any) -> Dict:
    elements = [item for item in _as_list(elements) if isinstance(item, dict)]
    default_kid = next(
        (item["@cenc:default_KID"] for item in elements if item.get("@cenc:default_KID")),
        None,
    )
    protection = {}
    for drm in elements:
        scheme = drm.get("@schemeIdUri")
        if scheme == WIDEVINE_UUID:
            pssh = _xml_text(drm.get("cenc:pssh"))
            key_id = drm.get("@cenc:default_KID") or default_kid
            if key_id is None and pssh:
                key_id = _widevine_key_id_from_pssh(pssh)
            widevine = protection.setdefault("widevine", {})
            if pssh:
                widevine["pssh"] = pssh
            if key_id:
                widevine["key_id"] = key_id
        elif scheme == PLAYREADY_UUID:
            pro = _xml_text(drm.get("mspr:pro"))
            if pro:
                protection.setdefault("playready", {})["pssh"] = pro
    return protection


def _parse_stream_segments(obj: Dict, template: Optional[Dict]) -> List[str]:
    if template is not None:
        return parse_segments(obj, template)
    # SegmentBase indexes byte ranges in one media file. Downloading BaseURL
    # in full includes both initialization and media without duplicating bytes.
    base_url = obj.get("BaseURL")
    if not base_url:
        raise ValueError("SegmentBase representation is missing BaseURL")
    return [base_url]


class Manifest(Object):
    """
    Info about a manifest.

    Parameters:
        video_streams (List of :obj:`~crunpyroll.types.ManifestVideoStream`):
            List of every video stream available.

        audio_streams (List of :obj:`~crunpyroll.types.ManifestAudioStream`):
            List of every audio stream available.

        subs_streams (List of :obj:`~crunpyroll.types.SubtitlesStream`):
            List of every subtitle stream available

        content_protection (:obj:`~crunpyroll.types.ContentProtection`):
            Info about Content Protection (DRM).

        plain (``str``):
            Plain version of the manifest (XML).
            Useful for external downloader tools.
    """

    def __init__(self, data: Dict):
        self.video_streams: List["ManifestVideoStream"] = data.get("video_streams") or []
        self.audio_streams: List["ManifestAudioStream"] = data.get("audio_streams") or []
        self.sub_streams: List["SubtitlesStream"] = data.get("subs_streams") or []
        self.content_protection: "ContentProtection" = ContentProtection(data.get("content_protection"))
        self.plain: str = data.get("plain")

    @classmethod
    def new_parse(cls, obj: str):
        return cls.parse(obj)

    @classmethod
    def parse(cls, obj: str):
        return cls._parse(obj)

    @classmethod
    def _parse(cls, obj: str):
        data = {
            "plain": obj,
            "video_streams": [],
            "audio_streams": [],
            "subs_streams": [],
            "content_protection": {},
        }
        manifest = xmltodict.parse(obj)
        for period in _as_list(manifest.get("MPD", {}).get("Period")):
            for aset in _as_list(period.get("AdaptationSet")):
                if not isinstance(aset, dict):
                    continue
                # DRM belongs to the adaptation, regardless of segment layout.
                protection = _parse_content_protection(aset.get("ContentProtection"))
                for system, metadata in protection.items():
                    data["content_protection"].setdefault(system, {}).update(metadata)
                mime_type = (
                    aset.get("@mimeType") or aset.get("@mime_Type")
                    or aset.get("@mime_type") or ""
                )
                for representation in _as_list(aset.get("Representation")):
                    if not isinstance(representation, dict):
                        continue
                    representation = dict(representation)
                    base_url = _xml_text(
                        representation.get("BaseURL") or aset.get("BaseURL")
                    )
                    if base_url is not None:
                        representation["BaseURL"] = base_url
                    mime = representation.get("@mimeType") or mime_type
                    template = representation.get(
                        "SegmentTemplate", aset.get("SegmentTemplate")
                    )
                    segment_base = representation.get("SegmentBase", aset.get("SegmentBase"))
                    if mime.startswith("video") or mime.startswith("audio"):
                        if template is None and segment_base is None:
                            continue
                        stream_type = (
                            ManifestVideoStream if mime.startswith("video")
                            else ManifestAudioStream
                        )
                        if template is not None:
                            stream = _safe_stream_parse(stream_type, representation, template)
                        else:
                            stream = stream_type.parse(representation, template)
                        if stream is not None:
                            target = "video_streams" if mime.startswith("video") else "audio_streams"
                            data[target].append(stream)
                    elif mime.startswith("text/vtt") and base_url:
                        data["subs_streams"].append(SubtitlesStream({
                            "format": "vtt", "language": aset.get("@lang", ""),
                            "url": base_url,
                        }))
        return cls(data)



class ManifestVideoStream(Object):
    """
    Info about a manifest video stream.

    Parameters:
        codecs (``str``):
            Codecs of the video stream.

        width (``int``):
            Width of the video stream.

        height (``int``):
            Height of the video stream.
        
        bitrate (``int``):
            Bitrate of the video stream.

        segments (List of ``str``):
            Each segment URL of the video stream. For SegmentBase manifests,
            contains the single complete media file URL, including initialization.
    """

    def __init__(self, data: Dict):
        self.codecs: str = data.get("codecs")
        self.width: int = data.get("width")
        self.height: int = data.get("height")
        self.bitrate: int = data.get("bitrate")
        self.segments: List[str] = data.get("segments")

    @classmethod
    def parse(cls, obj: Dict, template: Optional[Dict]):
        data = {}
        data["codecs"] = obj["@codecs"]
        data["width"] = int(obj["@width"])
        data["height"] = int(obj["@height"])
        data["bitrate"] = int(obj["@bandwidth"])
        data["segments"] = _parse_stream_segments(obj, template)
        return cls(data)


class ManifestAudioStream(Object):
    """
    Info about a manifest audio stream.

    Parameters:
        codecs (``str``):
            Codecs of the audio stream.
        
        bitrate (``int``):
            Bitrate of the audio stream.

        segments (List of ``str``):
            Each segment URL of the audio stream. For SegmentBase manifests,
            contains the single complete media file URL, including initialization.
    """

    def __init__(self, data: Dict):
        self.codecs: str = data.get("codecs")
        self.bitrate: int = data.get("bitrate")
        self.segments: List[str] = data.get("segments")

    @classmethod
    def parse(cls, obj: Dict, template: Optional[Dict]):
        data = {}
        data["codecs"] = obj["@codecs"]
        data["bitrate"] = int(obj["@bandwidth"])
        data["segments"] = _parse_stream_segments(obj, template)
        return cls(data)
