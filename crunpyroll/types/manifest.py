import base64
import traceback
from uuid import UUID

from .obj import Object
from .drm import ContentProtection
from crunpyroll.types import SubtitlesStream
from ..utils import (
    WIDEVINE_UUID,
    PLAYREADY_UUID,
    parse_segments
)

from typing import List, Dict, Any

import xmltodict


def _as_list(x: Any) -> list:
    """Normalize xmltodict single element (dict) or multiple (list) to a list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _node_text(value: Any) -> Any:
    """xmltodict 下，带内联 xmlns 声明的子元素会被解析成
    {'@xmlns:...': ..., '#text': ...} 结构，取其文本内容。"""
    if isinstance(value, dict):
        return value.get("#text")
    return value


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


def _extract_drm_info(aset: Dict, data: Dict) -> None:
    """Parse ContentProtection nodes of an AdaptationSet into data["content_protection"].

    与流格式无关：无论 AdaptationSet 使用 SegmentTemplate 还是
    BaseURL+SegmentBase（Crunchyroll 新打包格式），DRM 节点都直接
    挂在 AdaptationSet 下，必须无条件解析。key_id 优先取
    @cenc:default_KID，缺失时从 widevine pssh box 中解码。
    """
    for drm in _as_list(aset.get("ContentProtection")):
        if not isinstance(drm, dict):
            continue
        scheme_id_uri = drm.get("@schemeIdUri")
        if scheme_id_uri == WIDEVINE_UUID:
            widevine = data["content_protection"].setdefault("widevine", {})
            pssh = _node_text(drm.get("cenc:pssh"))
            if pssh:
                widevine["pssh"] = pssh
            key_id = drm.get("@cenc:default_KID")
            if not key_id and pssh:
                key_id = _widevine_key_id_from_pssh(pssh)
            if key_id:
                widevine["key_id"] = key_id
        if scheme_id_uri == PLAYREADY_UUID:
            playready = data["content_protection"].setdefault("playready", {})
            pro = _node_text(drm.get("mspr:pro"))
            if pro:
                playready["pssh"] = pro


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
        data = {}
        data["plain"] = obj
        data["video_streams"] = []
        data["audio_streams"] = []
        data["subs_streams"] = []
        data["content_protection"] = {}
        manifest = xmltodict.parse(obj)
        period = manifest.get("MPD", {}).get("Period") or {}
        for aset in _as_list(period.get("AdaptationSet")):
            if not isinstance(aset, dict):
                continue
            _extract_drm_info(aset, data)
            if "SegmentTemplate" in aset:
                template = aset["SegmentTemplate"]
                mime_type = aset.get("@mimeType") or aset.get("@mime_Type") or aset.get("@mime_type") or ""
                for repr in _as_list(aset.get("Representation")):
                    if not isinstance(repr, dict):
                        continue
                    if "video" in mime_type:
                        stream = _safe_stream_parse(ManifestVideoStream, repr, template)
                    elif "audio" in mime_type:
                        stream = _safe_stream_parse(ManifestAudioStream, repr, template)
                    else:
                        continue
                    if stream is not None:
                        data["video_streams" if isinstance(stream, ManifestVideoStream) else "audio_streams"].append(stream)
            else:
                mimeType = aset.get("@mimeType") or ""
                if mimeType.startswith("text/vtt"):
                    repr = aset.get("Representation")
                    if isinstance(repr, dict) and repr.get("BaseURL"):
                        stream = SubtitlesStream(dict(format='vtt', language=aset.get("@lang", ""), url=repr["BaseURL"]))
                        data["subs_streams"].append(stream)
        return cls(data)

    @classmethod
    def parse(cls, obj: str):
        data = {}
        data["plain"] = obj
        data["video_streams"] = []
        data["audio_streams"] = []
        data["subs_streams"] = []
        data["content_protection"] = {}
        manifest = xmltodict.parse(obj)
        period = manifest.get("MPD", {}).get("Period") or {}
        for aset in _as_list(period.get("AdaptationSet")):
            if not isinstance(aset, dict):
                continue
            _extract_drm_info(aset, data)
            if "SegmentTemplate" in aset:
                template = aset["SegmentTemplate"]
                for repr in _as_list(aset.get("Representation")):
                    if not isinstance(repr, dict):
                        continue
                    mime = (repr.get("@mimeType") or "")
                    if mime.startswith("video"):
                        stream = _safe_stream_parse(ManifestVideoStream, repr, template)
                    elif mime.startswith("audio"):
                        stream = _safe_stream_parse(ManifestAudioStream, repr, template)
                    else:
                        continue
                    if stream is not None:
                        data["video_streams" if isinstance(stream, ManifestVideoStream) else "audio_streams"].append(stream)
            else:
                mimeType = (aset.get("@mimeType") or "")
                if mimeType.startswith("text/vtt"):
                    repr = aset.get("Representation")
                    if isinstance(repr, dict) and repr.get("BaseURL"):
                        stream = SubtitlesStream(dict(format='vtt', language=aset.get("@lang", ""), url=repr["BaseURL"]))
                        data["subs_streams"].append(stream)
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
            Each segment URL of the video stream.
    """

    def __init__(self, data: Dict):
        self.codecs: str = data.get("codecs")
        self.width: int = data.get("width")
        self.height: int = data.get("height")
        self.bitrate: int = data.get("bitrate")
        self.segments: List[str] = data.get("segments")

    @classmethod
    def parse(cls, obj: Dict, template: Dict):
        data = {}
        data["codecs"] = obj["@codecs"]
        data["width"] = int(obj["@width"])
        data["height"] = int(obj["@height"])
        data["bitrate"] = int(obj["@bandwidth"])
        data["segments"] = parse_segments(obj, template)
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
            Each segment URL of the audio stream.
    """

    def __init__(self, data: Dict):
        self.codecs: str = data.get("codecs")
        self.bitrate: int = data.get("bitrate")
        self.segments: List[str] = data.get("segments")

    @classmethod
    def parse(cls, obj: Dict, template: Dict):
        data = {}
        data["codecs"] = obj["@codecs"]
        data["bitrate"] = int(obj["@bandwidth"])
        data["segments"] = parse_segments(obj, template)
        return cls(data)
