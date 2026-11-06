"""Pick the site adapter by the link. To add a site: write bot/<site>.py and list it here."""

import aiohttp

from bot import craigslist, krisha
from bot.listing import FetchError, Listing

SOURCES = (craigslist, krisha)


def is_search_url(url: str) -> bool:
    return any(s.is_search_url(url) for s in SOURCES)


async def fetch(session: aiohttp.ClientSession, url: str) -> list[Listing]:
    for s in SOURCES:
        if s.is_search_url(url):
            return await s.fetch(session, url)
    raise FetchError("unsupported site")
