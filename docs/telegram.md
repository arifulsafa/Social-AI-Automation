# Telegram bot setup

## Create the bot
1. Open Telegram, message `@BotFather`.
2. Send `/newbot`, pick a name and username.
3. Copy the token → `.env` → `TELEGRAM_BOT_TOKEN`.

## Lock it down
By default (empty `TELEGRAM_ALLOWED_USER_IDS`) the bot responds to anyone who finds it. For anything real:
1. Message `@userinfobot` to get your numeric user ID.
2. Set `TELEGRAM_ALLOWED_USER_IDS=<your_id>,<client_id>,...`.

## Run
```bash
python -m src.bots.telegram.bot
```
Leave it running. It uses long-polling — no public URL or webhook needed for dev.

## Commands
- `/new <niche>` — generate 7 drafts + images.
- `/review` — step through drafts. Buttons: Approve, Regenerate, Skip, Next.
- Free-text during review → treated as an edit instruction for the current post ("make it funnier", "shorter", "add a CTA").
- `/schedule` — push all approved drafts to Buffer.
- `/status` — counts by state for the current campaign.

## Production deployment
For retainer clients, run the bot as a long-lived process on a cheap VPS (Fly.io, Railway, $5 droplet). One bot per client, each with its own `.env` — keeps Buffer tokens and chat access isolated.

## WhatsApp later
The `src/bots/whatsapp/` directory is intentionally not built yet. When you add it:
- Start with **Twilio WhatsApp sandbox** — no business verification, good enough for the portfolio video.
- Move to **Meta WhatsApp Cloud API** once a paying client needs it. You'll need approved message templates for any bot-initiated message outside the 24-hour user-initiated window.
- Handlers should call the same `src/api/campaigns.py` functions the Telegram bot already uses — the business logic does not get duplicated.
