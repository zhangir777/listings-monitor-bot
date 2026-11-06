"""Krisha.kz search page -> listings. One page per request, browser User-Agent, public data only."""

import re
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from bot.listing import FetchError, Listing

BASE = "https://krisha.kz"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def is_search_url(url: str) -> bool:
    """Only krisha.kz rent/sale search pages, e.g. https://krisha.kz/arenda/kvartiry/almaty/"""
    p = urlparse(url.strip())
    return (
        p.scheme in ("http", "https")
        and p.hostname in ("krisha.kz", "www.krisha.kz")
        and p.path.startswith(("/arenda/", "/prodazha/"))
    )


def parse_price(text: str) -> int | None:
    digits = re.sub(r"\D", "", text.split("₸")[0])
    return int(digits) if digits else None


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for card in soup.select("div.a-card[data-id]"):
        link = card.select_one("a.a-card__title")
        if not link:
            continue
        price = card.select_one(".a-card__price")
        address = card.select_one(".a-card__subtitle")
        items.append(
            Listing(
                id=card["data-id"],
                title=" ".join(link.get_text().split()),
                price=parse_price(price.get_text()) if price else None,
                address=" ".join(address.get_text().split()) if address else "",
                url=BASE + link["href"],
                currency="₸",
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
