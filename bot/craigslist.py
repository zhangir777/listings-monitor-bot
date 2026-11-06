"""Craigslist search page -> listings. Static HTML page, browser User-Agent, public data only."""

import re
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from bot.listing import FetchError, Listing

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def is_search_url(url: str) -> bool:
    """Craigslist search pages, e.g. https://newyork.craigslist.org/search/apa?max_price=3000"""
    p = urlparse(url.strip())
    return (
        p.scheme in ("http", "https")
        and bool(p.hostname)
        and (p.hostname == "craigslist.org" or p.hostname.endswith(".craigslist.org"))
        and "/search/" in p.path
    )


def parse_price(text: str) -> int | None:
    digits = re.sub(r"\D", "", text.split(".")[0])
    return int(digits) if digits else None


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for card in soup.select("li.cl-static-search-result"):
        link = card.select_one("a[href]")
        if not link:
            continue
        title = card.select_one(".title")
        price = card.select_one(".price")
        place = card.select_one(".location")
        items.append(
            Listing(
                id=link["href"].rstrip("/").rsplit("/", 1)[-1],
                title=" ".join((title or link).get_text().split()),
                price=parse_price(price.get_text()) if price else None,
                address=" ".join(place.get_text().split()) if place else "",
                url=link["href"],
                currency="$",
            )
        )
    return items


async def fetch(session: aiohttp.ClientSession, url: str) -> list[Listing]:
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(30)) as r:
            if r.status != 200:
                raise FetchError(f"HTTP {r.status}")
            return parse_listings(await r.text())
    except (aiohttp.ClientError, TimeoutError) as e:
        raise FetchError(str(e)) from e
