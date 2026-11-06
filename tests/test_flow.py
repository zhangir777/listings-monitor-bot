"""/add -> /check -> new listing sent, through the real dispatcher with a fake Telegram API."""

import itertools
from datetime import datetime

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser

import bot.main as main
from bot.krisha import FetchError, Listing
from bot.storage import Storage

ids = itertools.count(1)
USER = TgUser(id=10, is_bot=False, first_name="Test", language_code="ru")
CHAT = Chat(id=10, type="private")
URL = "https://krisha.kz/arenda/kvartiry/almaty/?das[live.rooms]=1"


class FakeSession(BaseSession):
    """Records every API call and returns a plausible result."""

    def __init__(self):
        super().__init__()
        self.calls = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if method.__returning__ is bool:
            return True
        return Message(message_id=next(ids), date=datetime.now(), chat=CHAT, text="ok")

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    async def close(self):
        pass


def msg(text, user=USER):
    return Update(
        update_id=next(ids),
        message=Message(
            message_id=next(ids), date=datetime.now(), chat=CHAT, from_user=user, text=text
        ),
    )


def item(n, price=250000):
    return Listing(
        str(n), f"1-комн. кв #{n}", price, "Алмалинский р-н", f"https://krisha.kz/a/show/{n}"
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(main.router, "_parent_router", None)  # router is a module singleton
    monkeypatch.setattr(main, "store", Storage(tmp_path / "t.db"))
    monkeypatch.setattr(main, "allowed", set())
    monkeypatch.setattr(main, "PAUSE", 0)
    page = [item(1), item(2)]

    async def fake_fetch(session, url):
        if page is None:
            raise FetchError("HTTP 503")
        return list(page)

    monkeypatch.setattr(main, "fetcher", fake_fetch)
    session = FakeSession()
    bot = Bot("42:TEST", session=session)
    dp = Dispatcher()
    dp.include_router(main.router)

    async def feed(update):
        session.calls.clear()
        await dp.feed_update(bot, update)
        return [c for c in session.calls if isinstance(c, SendMessage)]

    feed.session = session
    return feed, page, monkeypatch


async def test_add_then_only_new_listings_sent(env):
    feed, page, _ = env
    sent = await feed(msg(f"/add {URL} 300 000"))
    assert "#1" in sent[0].text and "2" in sent[0].text

    sent = await feed(msg("/check"))
    assert sent[0].text == main.TEXTS["en"]["no_new"]

    page += [item(3), item(4, price=400000)]  # #4 is over the max price
    sent = await feed(msg("/check"))
    assert len(sent) == 1
    assert "1-комн. кв #3" in sent[0].text and "250 000 ₸" in sent[0].text
    assert "https://krisha.kz/a/show/3" in sent[0].text

    sent = await feed(msg("/check"))  # already sent -> not again
    assert sent[0].text == main.TEXTS["en"]["no_new"]


async def test_many_new_listings_are_summarized(env):
    feed, page, _ = env
    await feed(msg(f"/add {URL}"))
    page += [item(n) for n in range(10, 18)]
    sent = await feed(msg("/check"))
    assert len(sent) == main.MAX_SENT + 1
    assert "3" in sent[-1].text and URL in sent[-1].text


async def test_list_remove_and_validation(env):
    feed, _, _ = env
    assert (await feed(msg("/add https://evil.com/x")))[0].text == main.TEXTS["en"]["bad_url"]
    assert (await feed(msg(f"/add {URL} abc")))[0].text == main.TEXTS["en"]["bad_price"]
    assert (await feed(msg("/list")))[0].text == main.TEXTS["en"]["empty"]

    await feed(msg(f"/add {URL} 300000"))
    listing = (await feed(msg("/list")))[0].text
    assert "#1" in listing and "up to 300 000 ₸" in listing

    assert "deleted" in (await feed(msg("/remove 1")))[0].text
    assert "No search" in (await feed(msg("/remove 1")))[0].text
    assert (await feed(msg("/remove x")))[0].text == main.TEXTS["en"]["remove_usage"]


async def test_search_limit(env):
    feed, _, _ = env
    for _ in range(main.MAX_SEARCHES):
        await feed(msg(f"/add {URL}"))
    sent = await feed(msg(f"/add {URL}"))
    assert sent[0].text == main.TEXTS["en"]["too_many"].format(n=main.MAX_SEARCHES)


async def test_site_down_and_private_mode(env):
    feed, _, monkeypatch = env

    async def down(session, url):
        raise FetchError("HTTP 503")

    monkeypatch.setattr(main, "fetcher", down)
    assert (await feed(msg(f"/add {URL}")))[0].text == main.TEXTS["en"]["fetch_error"]

    monkeypatch.setattr(main, "allowed", {999})
    assert (await feed(msg("/start")))[0].text == main.TEXTS["en"]["closed"]


async def test_english_by_default_then_switch_language(env):
    feed, _, _ = env
    assert (await feed(msg("/start")))[0].text == main.TEXTS["en"]["start"]

    sent = await feed(msg("/language"))
    buttons = [b.callback_data for row in sent[0].reply_markup.inline_keyboard for b in row]
    assert buttons == ["lang:en", "lang:ru", "lang:kk"]

    m = Message(message_id=next(ids), date=datetime.now(), chat=CHAT, text="x")
    query = CallbackQuery(id="1", from_user=USER, chat_instance="1", message=m, data="lang:ru")
    await feed(Update(update_id=next(ids), callback_query=query))
    edits = [c for c in feed.session.calls if isinstance(c, EditMessageText)]
    assert edits[0].text == main.TEXTS["ru"]["start"]
    assert (await feed(msg("/list")))[0].text == main.TEXTS["ru"]["empty"]


async def test_stop_deletes_all_searches(env):
    feed, _, _ = env
    await feed(msg(f"/add {URL}"))
    await feed(msg(f"/add {URL} 100"))
    assert "Deleted 2" in (await feed(msg("/stop")))[0].text
    assert (await feed(msg("/list")))[0].text == main.TEXTS["en"]["empty"]
    assert "Deleted 0" in (await feed(msg("/stop")))[0].text
