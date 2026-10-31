from pathlib import Path

from bot.krisha import is_search_url, parse_listings, parse_price

HTML = (Path(__file__).parent / "fixtures" / "krisha_search.html").read_text(encoding="utf-8")


def test_parse_listings():
    items = parse_listings(HTML)
    assert [i.id for i in items] == ["1014873826", "1012394830", "690959289"]
    first = items[0]
    assert first.title == "1-комнатная квартира · 40 м² · 2/9 этаж"
    assert first.price == 260000
    assert first.address == "Бостандыкский р-н, Толе би 198"
    assert first.url == "https://krisha.kz/a/show/1014873826"
    assert all(i.price for i in items)


def test_parse_empty_page():
    assert parse_listings("<html><body>Nothing found</body></html>") == []


def test_parse_price():
    assert parse_price(" 260\xa0000\xa0₸ за месяц") == 260000
    assert parse_price("договорная") is None


def test_is_search_url():
    assert is_search_url("https://krisha.kz/arenda/kvartiry/almaty/?das[live.rooms]=1")
    assert is_search_url("https://krisha.kz/prodazha/doma/astana/")
    assert not is_search_url("https://krisha.kz/a/show/1014873826")
    assert not is_search_url("https://evil.com/arenda/kvartiry/")
    assert not is_search_url("https://krisha.kz.evil.com/arenda/")
    assert not is_search_url("krisha.kz/arenda/kvartiry/")
