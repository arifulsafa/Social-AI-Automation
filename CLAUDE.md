# Social AI Automation

A social-media scheduler that turns a topic/niche into a week of ready-to-post content, schedules it via Buffer, and is controllable from a phone through a Telegram or WhatsApp bot.

## What this project does

1. User sends a niche/topic (e.g. "vegan bakery in Austin") from Telegram/WhatsApp, a web form, or Make.com.
2. Claude generates **7 posts** for the week: caption + hashtags + image-generation prompt + platform recommendation (IG / X / LinkedIn / FB).
3. Images are generated from the prompts (via an image model; see `docs/images.md` when created).
4. Posts are pushed to Buffer via its API and scheduled across the week.
5. The user can review, approve, edit, or reschedule each post from their phone.

The pitch is "AI handles your social 24/7" — sold as a $100–300/mo retainer to small businesses.

## Architecture (target)

```
Telegram / WhatsApp bot ──┐
Web form / Make.com     ──┼──▶ API layer (FastAPI or Node)
                          │        │
                          │        ├──▶ Claude API  (content generation)
                          │        ├──▶ Image API   (image generation)
                          │        └──▶ Buffer MCP  (scheduling, GraphQL)
                          │
                          └──▶ Postgres / SQLite (posts, approvals, users)
```

- **Claude Computer Use is a fallback** for any platform without a public API (e.g. if Buffer's free tier doesn't cover what we need, or for direct IG/TikTok posting). Prefer real APIs first — Computer Use is slower, flakier, and more expensive.
- Bot layer is thin: it's a UI for the same API the web form hits. Don't duplicate business logic in the bot handlers.

## Directory layout (to be created)

```
src/
  generator/      # Claude prompt templates + post generation
  images/         # Image prompt → image file
  scheduler/      # Buffer MCP wrapper + scheduling logic
  bots/
    telegram/     # Telegram bot handlers
    whatsapp/     # WhatsApp (Twilio or Meta Cloud API) handlers
  api/            # HTTP endpoints (used by Make.com, web form, bots)
  db/             # Models + migrations
docs/
  setup.md        # 45-min setup guide for the portfolio demo
  buffer.md       # Buffer API auth + quirks
  telegram.md     # Bot setup
  whatsapp.md     # Twilio vs Meta Cloud API decision + setup
.env.example
```

## Core commands

*TBD — populate as the stack is chosen. Likely:*
- `uv run dev` or `npm run dev` — local server
- `uv run test` or `npm test` — tests
- `make seed` — seed a demo niche for the portfolio video

## Conventions

- **Secrets live in `.env`**, never committed. `.env.example` lists every required key: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TWILIO_*` or `WHATSAPP_*`, image-provider keys. Buffer auth is *not* in `.env` — it's a bearer token in the Buffer MCP server's header config (`~/.claude.json`). See `docs/buffer.md`.
- **One niche = one "campaign"** in the data model. A campaign owns 7 posts and a schedule. Store the Buffer `organizationId` on the campaign and the target `channelId`(s) on each post — both come from `list_channels` / `get_account`, never hard-coded.
- **Posts have states**: `draft → pending_approval → scheduled → posted | failed`. The bot drives state transitions.
- **Prompts are versioned files** under `src/generator/prompts/` so they can be A/B tested and improved without code changes.
- **Rate limits matter**: Buffer, Telegram, and WhatsApp all have them. Client wrappers must handle 429s with backoff.

## Phone-control layer (Telegram / WhatsApp)

The bot is the product's differentiator in the portfolio video — "approve a week of posts from your phone in 30 seconds." Minimum commands:

- `/new <niche>` — kick off generation.
- `/review` — show the 7 drafts one at a time with Approve / Edit / Regenerate / Skip buttons.
- `/schedule` — confirm the proposed schedule; allow shifting times.
- `/status` — show what's scheduled, posted, or failed this week.
- Free-text messages → treated as edit instructions for the currently-shown post ("make it funnier", "shorter", "add a CTA").

**Pick one channel first.** Telegram is faster to ship (official Bot API, no business verification). WhatsApp via Meta Cloud API requires a verified business and message-template approval for anything outside a 24-hour user-initiated window — real but slower. Twilio WhatsApp sandbox works for the demo video without verification.

## Non-goals (for v1)

- Multi-tenant billing / self-serve signup — manual onboarding is fine for the first 5 retainer clients.
- Analytics dashboards — Buffer already shows these; don't rebuild.
- Video / Reels generation — images only in v1.
- Direct posting to IG/TikTok/etc. — go through Buffer.
