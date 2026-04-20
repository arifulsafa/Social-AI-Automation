# 45-minute setup

## 1. Install deps
```bash
cd "Social AI Automation"
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Keys
Copy `.env.example` to `.env` and fill in:

| Key | Where to get it |
| --- | --- |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys |
| `GEMINI_API_KEY` | aistudio.google.com → "Get API key" |
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → `/newbot` |
| `TELEGRAM_ALLOWED_USER_IDS` | Telegram → @userinfobot → your numeric ID |

Buffer auth is **not** in `.env` — it's configured as an MCP server. Generate an API key at publish.buffer.com/settings/api, then register it:

```bash
claude mcp add buffer --transport http https://mcp.buffer.com/mcp \
  --header "Authorization: Bearer <YOUR_BUFFER_API_KEY>"
```

Channel IDs are discovered at runtime via the `list_channels` MCP tool — nothing to paste into `.env`. See `docs/buffer.md`.

## 3. Init DB
```bash
python -c "from src.db.models import init_db; init_db()"
```

## 4. Run the Telegram bot
```bash
python -m src.bots.telegram.bot
```

## 5. In Telegram, message your bot:
```
/new vegan bakery in Austin
/review        (tap Approve on each post)
/schedule
/status
```

## 6. (optional) Run the HTTP API for Make.com webhooks
```bash
uvicorn src.api.app:app --reload --port 8000
```
Then in Make.com create a scenario: Webhook → HTTP POST to `http://<ngrok-url>/campaigns` with `{ "niche": "...", "tone": "..." }`.
