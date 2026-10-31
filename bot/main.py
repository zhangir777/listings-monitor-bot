"""Krisha.kz listings monitor: saves a search and sends new listings to Telegram.

Run: uv run python -m bot.main
"""

import asyncio
import html
import logging
import os
from collections.abc import Awaitable, Callable

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BotCommand, CallbackQuery, LinkPreviewOptions, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from bot.krisha import FetchError, Listing, fetch, is_search_url
from bot.storage import Storage

MAX_SEARCHES = 5  # per chat
MAX_SENT = 5  # new listings sent per search per check, the rest are summarized
PAUSE = 3  # seconds between requests to the site
TEXTS = {
    "en": {
        "start": "Hi! I watch Krisha.kz and send you new listings as soon as they appear.\n\n"
        "1. Open krisha.kz, set filters (city, rooms, price) and copy the page link.\n"
        "2. Send: <code>/add LINK</code> or <code>/add LINK 300000</code> (max price, ₸).\n\n"
        "/list – your searches\n/remove N – delete search N\n/check – check now\n"
        "/language – change language",
        "bad_url": "Send a Krisha.kz search link, e.g.\n"
        "<code>/add https://krisha.kz/arenda/kvartiry/almaty/?das[live.rooms]=1 300000</code>",
        "bad_price": "Max price must be a number, e.g. 300000",
        "too_many": "Limit: {n} searches. Delete one with /remove N",
        "fetch_error": "Krisha.kz did not respond. Try again later.",
        "added": "✅ Search #{id} saved. Listings on the page now: {count}. "
        "I will send only new ones (checking every {minutes} min).",
        "empty": "No searches yet. Add one: /add LINK",
        "removed": "Search #{id} deleted.",
        "not_found": "No search #{id}. See /list",
        "remove_usage": "Usage: /remove N (number from /list)",
        "no_new": "No new listings yet.",
        "new": "🏠 New listing (search #{id})",
        "more": "…and {n} more new listings: {url}",
        "max": "up to {price}",
        "closed": "This bot is private.",
    },
    "ru": {
        "start": "Привет! Я слежу за Krisha.kz и присылаю новые объявления, как только они "
        "появляются.\n\n"
        "1. Откройте krisha.kz, выставьте фильтры (город, комнаты, цена) и скопируйте ссылку.\n"
        "2. Отправьте: <code>/add ССЫЛКА</code> или <code>/add ССЫЛКА 300000</code> "
        "(макс. цена, ₸).\n\n"
        "/list – ваши поиски\n/remove N – удалить поиск N\n/check – проверить сейчас\n"
        "/language – сменить язык",
        "bad_url": "Пришлите ссылку на поиск Krisha.kz, например\n"
        "<code>/add https://krisha.kz/arenda/kvartiry/almaty/?das[live.rooms]=1 300000</code>",
        "bad_price": "Макс. цена должна быть числом, например 300000",
        "too_many": "Лимит: {n} поисков. Удалите один через /remove N",
        "fetch_error": "Krisha.kz не ответил. Попробуйте позже.",
        "added": "✅ Поиск #{id} сохранён. Объявлений на странице сейчас: {count}. "
        "Буду присылать только новые (проверка каждые {minutes} мин).",
        "empty": "Поисков пока нет. Добавьте: /add ССЫЛКА",
        "removed": "Поиск #{id} удалён.",
        "not_found": "Поиска #{id} нет. Смотрите /list",
        "remove_usage": "Формат: /remove N (номер из /list)",
        "no_new": "Новых объявлений пока нет.",
        "new": "🏠 Новое объявление (поиск #{id})",
        "more": "…и ещё {n} новых: {url}",
        "max": "до {price}",
        "closed": "Это приватный бот.",
    },
    "kk": {
        "start": "Сәлем! Мен Krisha.kz сайтын бақылап, жаңа хабарландыруларды бірден жіберемін.\n\n"
        "1. krisha.kz ашып, сүзгілерді (қала, бөлме, баға) қойып, сілтемені көшіріңіз.\n"
        "2. Жіберіңіз: <code>/add СІЛТЕМЕ</code> немесе <code>/add СІЛТЕМЕ 300000</code> "
        "(макс. баға, ₸).\n\n"
        "/list – іздеулеріңіз\n/remove N – N іздеуді өшіру\n/check – қазір тексеру\n"
        "/language – тілді ауыстыру",
        "bad_url": "Krisha.kz іздеу сілтемесін жіберіңіз, мысалы\n"
        "<code>/add https://krisha.kz/arenda/kvartiry/almaty/?das[live.rooms]=1 300000</code>",
        "bad_price": "Макс. баға сан болуы керек, мысалы 300000",
        "too_many": "Шектеу: {n} іздеу. Біреуін /remove N арқылы өшіріңіз",
        "fetch_error": "Krisha.kz жауап бермеді. Кейінірек көріңіз.",
        "added": "✅ #{id} іздеу сақталды. Қазір бетте хабарландыру саны: {count}. "
        "Тек жаңаларын жіберемін (әр {minutes} мин сайын тексеремін).",
        "empty": "Іздеулер әлі жоқ. Қосыңыз: /add СІЛТЕМЕ",
        "removed": "#{id} іздеу өшірілді.",
        "not_found": "#{id} іздеу жоқ. /list қараңыз",
        "remove_usage": "Пішімі: /remove N (/list ішіндегі нөмір)",
        "no_new": "Әзірге жаңа хабарландыру жоқ.",
        "new": "🏠 Жаңа хабарландыру (#{id} іздеу)",
        "more": "…тағы {n} жаңа: {url}",
        "max": "{price} дейін",
        "closed": "Бұл жеке бот.",
    },
}
LANGS = {"en": "🇬🇧 English", "ru": "🇷🇺 Русский", "kk": "🇰🇿 Қазақша"}
COMMANDS = [
    ("start", "How it works"),
    ("list", "My searches"),
    ("check", "Check now"),
    ("language", "Change language"),
]

router = Router()
store: Storage | None = None
session: aiohttp.ClientSession | None = None
allowed: set[int] = set()
interval = 15  # minutes
fetcher: Callable[[aiohttp.ClientSession, str], Awaitable[list[Listing]]] = fetch


def lang_of(message: Message) -> str:
    """Language chosen with /language, English by default."""
    return store.get_lang(message.chat.id)


def t(lang: str, key: str, **kw) -> str:
    return TEXTS[lang][key].format(**kw)


def fmt_price(price: int | None) -> str:
    return f"{price:,}".replace(",", " ") + " ₸" if price else "—"


def card(lang: str, search_id: int, item: Listing) -> str:
    return (
        f"<b>{t(lang, 'new', id=search_id)}</b>\n{html.escape(item.title)}\n"
        f"💰 {fmt_price(item.price)}\n📍 {html.escape(item.address)}\n{item.url}"
    )


async def check_search(bot: Bot, search: tuple[int, int, str, int | None]) -> int:
    """Fetch one search page, send new listings that fit the price. Returns how many were new."""
    search_id, chat_id, url, max_price = search
    lang = store.get_lang(chat_id)
    items = await fetcher(session, url)
    fresh = set(store.new_ids(search_id, [i.id for i in items]))
    new = [i for i in items if i.id in fresh and (not max_price or (i.price or 0) <= max_price)]
    for item in new[:MAX_SENT]:
        await bot.send_message(chat_id, card(lang, search_id, item))
    if len(new) > MAX_SENT:
        await bot.send_message(chat_id, t(lang, "more", n=len(new) - MAX_SENT, url=url))
    return len(new)


def closed(message: Message) -> bool:
    return bool(allowed) and message.chat.id not in allowed


@router.message(CommandStart())
@router.message(Command("help"))
async def start(message: Message):
    lang = lang_of(message)
    await message.answer(t(lang, "closed" if closed(message) else "start"))


@router.message(Command("language"))
async def language(message: Message):
    kb = InlineKeyboardBuilder()
    for code, name in LANGS.items():
        kb.button(text=name, callback_data=f"lang:{code}")
    await message.answer(
        "Choose language / Выберите язык / Тілді таңдаңыз", reply_markup=kb.as_markup()
    )


@router.callback_query(F.data.startswith("lang:"))
async def set_language(call: CallbackQuery):
    code = call.data.split(":", 1)[1]
    if code not in TEXTS:
        return await call.answer()
    store.set_lang(call.message.chat.id, code)
    await call.answer()
    await call.message.edit_text(t(code, "closed" if closed(call.message) else "start"))


@router.message(Command("add"))
async def add(message: Message, command: CommandObject):
    lang = lang_of(message)
    if closed(message):
        return await message.answer(t(lang, "closed"))
    parts = (command.args or "").split()
    if not parts or not is_search_url(parts[0]):
        return await message.answer(t(lang, "bad_url"))
    max_price = None
    if len(parts) > 1:
        digits = "".join(parts[1:]).replace("_", "")
        if not digits.isdigit():
            return await message.answer(t(lang, "bad_price"))
        max_price = int(digits)
    if len(store.searches(message.chat.id)) >= MAX_SEARCHES:
        return await message.answer(t(lang, "too_many", n=MAX_SEARCHES))
    try:
        items = await fetcher(session, parts[0])
    except FetchError as e:
        logging.warning("add: %s", e)
        return await message.answer(t(lang, "fetch_error"))
    search_id = store.add_search(message.chat.id, parts[0], max_price)
    store.new_ids(search_id, [i.id for i in items])  # current page = already seen
    await message.answer(
        t(lang, "added", id=search_id, count=len(items), minutes=interval),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.message(Command("list"))
async def list_searches(message: Message):
    lang = lang_of(message)
    if closed(message):
        return await message.answer(t(lang, "closed"))
    rows = store.searches(message.chat.id)
    if not rows:
        return await message.answer(t(lang, "empty"))
    lines = [
        f"#{sid} {html.escape(url)}" + (f" ({t(lang, 'max', price=fmt_price(mp))})" if mp else "")
        for sid, _, url, mp in rows
    ]
    await message.answer(
        "\n\n".join(lines), link_preview_options=LinkPreviewOptions(is_disabled=True)
    )


@router.message(Command("remove"))
async def remove(message: Message, command: CommandObject):
    lang = lang_of(message)
    if closed(message):
        return await message.answer(t(lang, "closed"))
    arg = (command.args or "").strip().lstrip("#")
    if not arg.isdigit():
        return await message.answer(t(lang, "remove_usage"))
    ok = store.remove_search(message.chat.id, int(arg))
    await message.answer(t(lang, "removed" if ok else "not_found", id=arg))


@router.message(Command("check"))
async def check(message: Message):
    lang = lang_of(message)
    if closed(message):
        return await message.answer(t(lang, "closed"))
    rows = store.searches(message.chat.id)
    if not rows:
        return await message.answer(t(lang, "empty"))
    total = 0
    for i, row in enumerate(rows):
        if i:
            await asyncio.sleep(PAUSE)
        try:
            total += await check_search(message.bot, row)
        except FetchError as e:
            logging.warning("check #%s: %s", row[0], e)
            return await message.answer(t(lang, "fetch_error"))
    if not total:
        await message.answer(t(lang, "no_new"))


async def poll(bot: Bot):
    """Check every saved search every `interval` minutes, one page per search."""
    while True:
        await asyncio.sleep(interval * 60)
        for row in store.searches():
            try:
                await check_search(bot, row)
            except Exception:
                logging.exception("poll search #%s", row[0])
            await asyncio.sleep(PAUSE)


async def main():
    global store, session, allowed, interval
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = Storage(os.getenv("DB_FILE", "data/monitor.db"))
    allowed = {int(x) for x in os.getenv("ALLOWED_IDS", "").replace(" ", "").split(",") if x}
    interval = max(10, int(os.getenv("CHECK_INTERVAL", "15")))  # be polite to the site
    bot = Bot(os.environ["BOT_TOKEN"], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS])
    dp = Dispatcher()
    dp.include_router(router)
    async with aiohttp.ClientSession() as s:
        session = s
        task = asyncio.create_task(poll(bot))
        try:
            await dp.start_polling(bot)
        finally:
            task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
