# Social AI Automation

Turn any niche into a week of scheduled social media posts — controlled from your phone.

Send `/new vegan bakery in Austin` to a Telegram bot. Claude generates 7 posts (captions, hashtags, images). You review and approve each one. They go straight to Buffer and post themselves across the week.

Sold as a $100–300/mo retainer to small businesses.

---

## How it works

```
Telegram bot
    │
    ▼
FastAPI layer
    ├── Claude API      → generates 7 posts (captions + hashtags + image prompts)
    ├── Gemini Flash    → renders images from prompts
    └── Buffer GraphQL  → schedules posts across the week
```

Posts move through states: `draft → pending_approval → scheduled → posted`.

---

## Quick start

**Prerequisites:** Python 3.12+, a Telegram bot token, Anthropic API key, Gemini API key, Buffer API key.

```bash
git clone <this-repo>
cd "Social AI Automation"
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in:

| Key | Where to get it |
| --- | --- |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys |
| `GEMINI_API_KEY` | aistudio.google.com → Get API key |
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → `/newbot` |
| `TELEGRAM_ALLOWED_USER_IDS` | Telegram → @userinfobot → your numeric ID |
| `BUFFER_API_KEY` | publish.buffer.com/settings/api |

Register the Buffer MCP server (one-time):

```bash
claude mcp add buffer --transport http https://mcp.buffer.com/mcp \
  --header "Authorization: Bearer <YOUR_BUFFER_API_KEY>"
```

Init the database and start the bot:

```bash
python -c "from src.db.models import init_db; init_db()"
python -m src.bots.telegram.bot
```

Full setup walkthrough: [docs/setup.md](docs/setup.md)

---

## Telegram commands

| Command | What it does |
| --- | --- |
| `/new <niche>` | Generate a week of posts for the niche |
| `/review` | Step through drafts — Approve / Regenerate / Skip |
| `/schedule` | Push approved posts to Buffer |
| `/status` | Show what's scheduled, posted, or failed |
| Free text | Edit instruction for the current post ("make it funnier") |

---

## Project layout

```
src/
  generator/      # Claude prompt templates + post generation
  images/         # Gemini image generation
  scheduler/      # Buffer GraphQL client + scheduling logic
  bots/telegram/  # Telegram bot handlers
  api/            # FastAPI endpoints (Make.com / web form)
  db/             # SQLModel models + migrations
docs/
  setup.md        # Full setup guide
  buffer.md       # Buffer API auth + quirks
  telegram.md     # Bot setup
```

---

## Optional: HTTP API for Make.com / web forms

```bash
uvicorn src.api.app:app --reload --port 8000
```

POST to `/campaigns` with `{ "niche": "...", "tone": "..." }` to kick off generation without the bot.
