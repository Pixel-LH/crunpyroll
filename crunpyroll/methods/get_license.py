from crunpyroll import types
from crunpyroll import enums

import crunpyroll

class GetLicense:
    async def get_license(
        self: "crunpyroll.Client",
        media_id: str,
        *,
        challenge: bytes,
        token: str,
    ) -> bytes:
        """
        Get DRM license. Useful to obtain decryption keys.

        .. todo::

            Add support for PlayReady DRM

        Parameters:
            media_id (``str``):
                Unique identifier of a media.
            challenge (``bytes``):
                Challenge provided by CDM.
            token (``str``):
                Token of the stream.

        Returns:
            ``bytes``:
                On success, raw license bytes are returned.
        """
        await self.session.retrieve()
        response = await self.api_request(
            method="POST",
            endpoint="v1/license/widevine",
            params={"specConform": True},
            headers={
                "Content-Type": "application/octet-stream",
                "X-Cr-Content-Id": media_id,
                "X-Cr-Video-Token": token,
            },
            host=enums.APIHost.LICENSE,
            payload=challenge,
            raw=True,
        )
        return response