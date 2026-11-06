from pathlib import Path

from bot import sources
from bot.craigslist import is_search_url, parse_listings, parse_price

HTML = (Path(__file__).parent / "fixtures" / "craigslist_search.html").read_text(encoding="utf-8")


def test_parse_listings():
    items = parse_listings(HTML)
    assert len(items) > 50
    first = items[0]
    assert first.id == "ik1unBkbJjuY5pxV8Rnk8D"
    assert first.title == "Stylish Bensonhurst 2 Bedroom Apartment For Rent"
    assert first.price == 1700
    assert first.address == "Bensonhurst"
    assert first.url.startswith("https://www.craigslist.org/view/")
    assert first.currency == "$"
    assert len({i.id for i in items}) == len(items)


def test_parse_empty_page():
    assert parse_listings("<html><body>Nothing found</body></html>") == []


def test_parse_price():
    assert parse_price("$1,700") == 1700
    assert parse_price("$2,450.50") == 2450
    assert parse_price("") is None


def test_is_search_url():
    assert is_search_url("https://newyork.craigslist.org/search/apa?max_price=3000")
    assert not is_search_url("https://newyork.craigslist.org/")
    assert not is_search_url("https://evil.com/search/apa?x=craigslist.org")
    assert not is_search_url("https://craigslist.org.evil.com/search/apa")


def test_sources_dispatch():
    assert sources.is_search_url("https://newyork.craigslist.org/search/apa")
    assert sources.is_search_url("https://krisha.kz/arenda/kvartiry/almaty/")
    assert not sources.is_search_url("https://example.com/search/")
