from crunpyroll import types
from crunpyroll import enums

import crunpyroll

class GetSkipEvents:
    async def get_skip_events(
        self: "crunpyroll.Client",
        episode_id: str,
    ) -> "types.SkipEvents":
        """
        Get skip events (intro, recap, credits, etc.) for an episode.

        Fetches the static JSON from Crunchyroll CDN. No session auth required.

        Parameters:
            episode_id (``str``):
                Episode identifier (same as media_id for playback).

        Returns:
            :obj:`~crunpyroll.types.SkipEvents`:
                On success, skip events are returned.
        """
        await self.session.retrieve()
        response = await self.api_request(
            method="GET",
            endpoint="skip-events/production/" + episode_id + ".json",
            host=enums.APIHost.STATIC,
            include_session=False,
        )
        return types.SkipEvents.parse(response)
