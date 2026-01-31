from crunpyroll import types
from crunpyroll import enums

import crunpyroll
from crunpyroll.errors import CrunpyrollException

class GetStreams:
    async def get_streams(
        self: "crunpyroll.Client",
        media_id: str,
        *,
        locale: str = None,
        stream_endpoint: str = "tv",
    ) -> "types.MediaStreams":
        """
        Get available streams of a media.

        Parameters:
            media_id (``str``):
                Unique identifier of the media.
            locale (``str``, *optional*):
                Localize request for different results.
                Default to the one used in Client.
            stream_endpoint (``str``, *optional*):
                Endpoint to use: ``"tv"`` for TV playback (default),
                ``"phone"`` for phone/download (typically 192kbps AAC).
                TV uses PLAY_SERVICE; phone tries www first, then falls back
                to PLAY_SERVICE + v1 if www returns 403 (e.g. Cloudflare).

        Returns:
            :obj:`~crunpyroll.types.MediaStreams`:
                On success, streams are returned.
        """
        await self.session.retrieve()
        if stream_endpoint == "phone":
            params_phone = {"locale": locale or self.preferred_audio_language}
            try:
                response = await self.api_request(
                    method="GET",
                    endpoint="playback/v2/" + media_id + "/android/phone/download",
                    params=params_phone,
                    host=enums.APIHost.WEB,
                )
            except CrunpyrollException:
                response = await self.api_request(
                    method="GET",
                    endpoint="v1/" + media_id + "/android/phone/download",
                    params={
                        "locale": locale or self.preferred_audio_language,
                        "queue": False,
                    },
                    host=enums.APIHost.PLAY_SERVICE,
                )
            return types.MediaStreams.parse(response, media_id)
        else:
            host = enums.APIHost.PLAY_SERVICE
            endpoint = "v1/" + media_id + "/tv/android_tv/play"
            params = {
                "locale": locale or self.preferred_audio_language,
                "queue": False,
            }
            response = await self.api_request(
                method="GET",
                endpoint=endpoint,
                params=params,
                host=host,
            )
            return types.MediaStreams.parse(response, media_id)

    async def get_streams_phone(
        self: "crunpyroll.Client",
        media_id: str,
        *,
        locale: str = None,
    ) -> "types.MediaStreams":
        """
        Get streams from the phone/download endpoint (typically 192kbps AAC).

        Tries www first; on 403 (e.g. Cloudflare) falls back to PLAY_SERVICE.
        Convenience wrapper for dual-endpoint usage: use TV streams for video
        and phone streams for high-bitrate audio.

        Parameters:
            media_id (``str``):
                Unique identifier of the media.
            locale (``str``, *optional*):
                Localize request. Default to Client preferred_audio_language.

        Returns:
            :obj:`~crunpyroll.types.MediaStreams`:
                On success, streams are returned.
        """
        return await self.get_streams(
            media_id,
            locale=locale,
            stream_endpoint="phone",
        )
            