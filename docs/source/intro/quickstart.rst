Quick Start
===========

The next few steps serve as a quick start to see Crunpyroll in action.

Example
----------------------

Here's a quick example code. This script will login into the account, search for Attack on Titan series, and print the seasons of the show.
    
    .. code-block:: python

        import crunpyroll
        import asyncio

        client = crunpyroll.Client(
            email="email",
            password="password",
            locale="it-IT"
        )
        async def main():
            # Start client and login
            await client.start()
            # Search for Attack on Titan
            query = await client.search("Attack On Titan")
            series_id = query.items[0].id
            print(series_id)
            # Retrieve all seasons of the series
            seasons = await client.get_seasons(series_id)
            print(seasons)

        asyncio.run(main())

Smart Chapters and 192kbps audio
--------------------------------

**Skip events (chapters):** Use :meth:`~crunpyroll.Client.get_skip_events` with an episode id to fetch skip-events JSON from Crunchyroll's static CDN. Then use :func:`~crunpyroll.types.skip_events.build_chapter_list` on the returned :obj:`~crunpyroll.types.SkipEvents.events` to build a named chapter list (Intro, Recap, Chapter 1, Credits, etc.) with gap detection and correct ordering so that "Chapter 1" follows after Intro/Recap.

**192kbps audio (dual-endpoint):** Use :meth:`~crunpyroll.Client.get_streams` with ``stream_endpoint="phone"`` or the convenience method :meth:`~crunpyroll.Client.get_streams_phone` to get streams from the phone/download endpoint, which typically provides 192kbps AAC. For dual-endpoint usage: get TV streams for video with the default ``get_streams(media_id)`` and phone streams for audio with ``get_streams_phone(media_id)``; merge manifests in your download pipeline.

Enjoy the API
-------------

That was just a quick overview. In the next few pages of the introduction, we'll take a much more in-depth look of what
we have just done above.