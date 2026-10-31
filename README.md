# Listings monitor bot for Telegram (Krisha.kz)

[![CI](https://github.com/zhangir777/listings-monitor-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/zhangir777/listings-monitor-bot/actions/workflows/ci.yml)

**Hire me:** [Upwork](https://www.upwork.com/freelancers/~012c68804f9b4d4550) · [Fiverr](https://www.fiverr.com/akhmetov_zhangi) · [Telegram @ZhangirAkhmetov](https://t.me/ZhangirAkhmetov)

**Live demo:** [@zhangir_monitor_bot](https://t.me/zhangir_monitor_bot) (runs when my demo server is on)

A Telegram bot that watches your Krisha.kz search and sends **only new listings** the moment
they appear: title, price, address and link. Good for renters, buyers and realtors who don't
want to refresh the site all day.

- Paste any Krisha.kz search link with your filters (city, rooms, price, district).
- Optional max price: `/add LINK 300000`.
- Remembers what was already sent (SQLite), so you never get the same listing twice.
- Polite to the site: one page per search, every 15 min by default (minimum 10), pauses between requests.
- Russian, Kazakh and English (picked from the Telegram app language).
- Private mode: `ALLOWED_IDS` limits the bot to you or your team.

## Commands
| Command | What it does |
|---|---|
| `/start` | How to use |
| `/add LINK [max price]` | Save a search (current listings are marked as seen) |
| `/list` | Your searches |
| `/remove N` | Delete search N |
| `/check` | Check now instead of waiting |

## Run
1. Copy `.env.example` to `.env` and set `BOT_TOKEN` (from @BotFather).
2. Run:
   ```
   uv sync
   uv run python -m bot.main
   ```
   or with Docker: `docker compose up -d --build`

## Tests
```
uv run pytest -q
```
Parser tests use a saved Krisha.kz page (`tests/fixtures`), so they don't hit the site.

## Other sites
`bot/krisha.py` is the only site-specific file. For another site (OLX, Kolesa, etc.) write a
module with the same `fetch()` that returns `Listing` objects. Only public pages, no login,
no bypassing blocks.

## License
MIT
