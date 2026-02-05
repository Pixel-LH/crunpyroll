from typing import Callable, Dict, Any, Iterable, Optional, Set

import crunpyroll
from crunpyroll import enums, types
from crunpyroll.errors import CrunpyrollException


class GetStreams:
    """
    提供获取音视频流的统一入口，支持：
    - TV 端播放（android_tv/play）
    - 手机端 / 下载端点（android/phone/download）
    - 按指定语言优先选择音轨（locale）
    - 若找不到匹配语言，打印当前可用的所有音轨语言
    """

    # --------------------------- 公共入口 --------------------------- #
    async def get_streams(
        self: "crunpyroll.Client",
        media_id: str,
        *,
        locale: str | None = None,
        stream_endpoint: str = "tv",
    ) -> "types.MediaStreams":
        """
        获取指定媒资的音视频流。

        参数:
            media_id (str): 媒资 ID。
            locale (str, 可选): 希望的音轨语言，例如 "en" 或 "en-US"。
                               若为短码（en），会优先匹配以该前缀开头的语言（en-US、en-GB 等）。
                               若为完整码（en-US），则要求完全相等。
            stream_endpoint (str, 可选): "tv" 或 "phone"。
                - "tv"   -> /tv/android_tv/play（默认）
                - "phone"-> /android/phone/download（192kbps AAC）
        返回:
            types.MediaStreams: 解析后的流信息。
        """
        await self.session.retrieve()

        if stream_endpoint == "phone":
            return await self._get_streams_phone_internal(media_id, locale=locale)
        else:
            return await self._get_streams_tv_internal(media_id, locale=locale)

    async def get_streams_phone(
        self: "crunpyroll.Client",
        media_id: str,
        *,
        locale: str | None = None,
    ) -> "types.MediaStreams":
        """
        手机 / 下载端点的快捷封装，等价于:

            await client.get_streams(media_id, locale=..., stream_endpoint="phone")
        """
        return await self.get_streams(
            media_id,
            locale=locale,
            stream_endpoint="phone",
        )

    # --------------------------- 内部实现：TV --------------------------- #
    async def _get_streams_tv_internal(
        self: "crunpyroll.Client",
        media_id: str,
        *,
        locale: str | None,
    ) -> "types.MediaStreams":
        host = enums.APIHost.PLAY_SERVICE
        endpoint = f"v1/{media_id}/tv/android_tv/play"
        params: Dict[str, Any] = {
            "locale": locale or self.preferred_audio_language,
            "queue": False,
        }

        # 第一次使用原始 media_id 请求
        response: Dict[str, Any] = await self.api_request(
            method="GET",
            endpoint=endpoint,
            params=params,
            host=host,
        )
        streams = types.MediaStreams.parse(response, media_id)

        # 如果没有指定 locale，直接返回
        if not locale:
            return streams

        # 根据 locale 尝试在 versions 里找到合适 guid 并重试一次
        def build_endpoint(guid: str) -> str:
            return f"v1/{guid}/tv/android_tv/play"

        return await self._maybe_retry_with_locale(
            media_id=media_id,
            desired_locale=locale,
            initial_streams=streams,
            initial_response=response,
            host=host,
            params=params,
            build_endpoint=build_endpoint,
        )

    # --------------------------- 内部实现：Phone --------------------------- #
    async def _get_streams_phone_internal(
        self: "crunpyroll.Client",
        media_id: str,
        *,
        locale: str | None,
    ) -> "types.MediaStreams":
        """
        Phone / 下载端点:
        - 优先走 playback/v2/{media_id}/android/phone/download (host=WEB)
        - 若抛出 CrunpyrollException（例如 403 Cloudflare），
          则回退到 v1/{media_id}/android/phone/download (host=PLAY_SERVICE)
        同样支持根据 locale 在 versions 中查找对应 guid 并重试。
        """
        # 先尝试 WEB 的 playback/v2
        params_www: Dict[str, Any] = {
            "locale": locale or self.preferred_audio_language,
        }

        try:
            endpoint = f"playback/v2/{media_id}/android/phone/download"
            host = enums.APIHost.WEB
            response: Dict[str, Any] = await self.api_request(
                method="GET",
                endpoint=endpoint,
                params=params_www,
                host=host,
            )
            params_used = params_www

            def build_endpoint(guid: str) -> str:
                return f"playback/v2/{guid}/android/phone/download"

        except CrunpyrollException:
            # 回退到 PLAY_SERVICE v1
            params_v1: Dict[str, Any] = {
                "locale": locale or self.preferred_audio_language,
                "queue": False,
            }
            endpoint = f"v1/{media_id}/android/phone/download"
            host = enums.APIHost.PLAY_SERVICE
            response = await self.api_request(
                method="GET",
                endpoint=endpoint,
                params=params_v1,
                host=host,
            )
            params_used = params_v1

            def build_endpoint(guid: str) -> str:
                return f"v1/{guid}/android/phone/download"

        streams = types.MediaStreams.parse(response, media_id)

        # 未指定 locale，直接返回
        if not locale:
            return streams

        # 指定了 locale，则尝试根据 versions 里的 audio_locale 选 guid 重试
        return await self._maybe_retry_with_locale(
            media_id=media_id,
            desired_locale=locale,
            initial_streams=streams,
            initial_response=response,
            host=host,
            params=params_used,
            build_endpoint=build_endpoint,
        )

    # --------------------------- 公共辅助逻辑 --------------------------- #
    async def _maybe_retry_with_locale(
        self: "crunpyroll.Client",
        *,
        media_id: str,
        desired_locale: str,
        initial_streams: "types.MediaStreams",
        initial_response: Dict[str, Any],
        host: "enums.APIHost",
        params: Dict[str, Any],
        build_endpoint: Callable[[str], str],
    ) -> "types.MediaStreams":
        """
        若 initial_streams 的 audio_locale 与 desired_locale 不符，则：
        1. 从 initial_response["versions"] 中查找 audio_locale 匹配的版本
           - 若 desired_locale 是短码（如 "en"），则用前缀匹配 (starts with)
           - 若 desired_locale 包含 '-'（如 "en-US"），则要求全等
        2. 若找到合适 guid，则用该 guid 构建 endpoint 重试一次并返回其结果
        3. 若仍未找到，则打印当前所有可用的 audio_locale 列表，返回 initial_streams
        """

        def _match(lang: Optional[str]) -> bool:
            if not isinstance(lang, str):
                return False
            if "-" in desired_locale:
                return lang.lower() == desired_locale.lower()
            return lang.lower().startswith(desired_locale.lower())

        current_locale = getattr(initial_streams, "audio_locale", None)
        if current_locale and _match(current_locale):
            # 第一次就已经是想要的语言
            return initial_streams

        versions: Iterable[Dict[str, Any]] = []
        if isinstance(initial_response, dict):
            raw_versions = initial_response.get("versions") or []
            if isinstance(raw_versions, list):
                versions = [v for v in raw_versions if isinstance(v, dict)]

        # 在 versions 中查找目标语言
        target_guid: Optional[str] = None
        for ver in versions:
            if _match(ver.get("audio_locale")):
                target_guid = ver.get("guid")
                break

        if target_guid:
            endpoint_guid = build_endpoint(target_guid)
            response_guid: Dict[str, Any] = await self.api_request(
                method="GET",
                endpoint=endpoint_guid,
                params=params,
                host=host,
            )
            return types.MediaStreams.parse(response_guid, target_guid)

        # 没有找到匹配的语言，打印当前可用的所有 audio_locale，方便调试
        available_locales: Set[str] = {
            v.get("audio_locale")
            for v in versions
            if isinstance(v, dict) and v.get("audio_locale")
        }
        if available_locales:
            print(
                f"[Crunpyroll] No streams found for requested locale "
                f"'{desired_locale}' on media_id '{media_id}'. "
                f"Available audio locales: {sorted(available_locales)}"
            )

        return initial_streams
