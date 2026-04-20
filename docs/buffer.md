# Buffer integration notes

## Auth model
We use the **Buffer MCP server** (GraphQL API) instead of the classic REST API. It's installed via:

```
claude mcp add buffer --transport http https://mcp.buffer.com/mcp \
  --header "Authorization: Bearer <API_KEY>"
```

The API key is generated at https://publish.buffer.com/settings/api and scoped to the user's Buffer account/organization. No OAuth dance needed — the bearer token is enough.

For retainer clients: each client generates their own key from their own Buffer account, and we register a separate MCP connection per client (or swap the header at runtime — TBD when we have more than one client).

## Core concepts (GraphQL model)
- **Organization** — a Buffer workspace. A user may have several; `get_account` returns them. Always confirm which org we're operating in before creating posts.
- **Channel** — one connected social account (IG, X, LinkedIn, etc.). Replaces the old "profile" concept. List with `list_channels`; never hard-code or guess IDs.
- **Post** — scheduled or published content on one or more channels.
- **Idea** — a draft/concept captured for later (`create_idea`).

## Typical workflow (via MCP tools)
1. `get_account` → pick the organization, note its timezone.
2. `list_channels` → pick the `channelId`s for the post's target platforms.
3. `get_channel` (optional) → inspect posting schedule before scheduling.
4. `create_post` → defaults to `addToQueue`; pass an ISO 8601 `dueAt` in the account's timezone for specific times.
5. For anything the canned tools don't cover, `introspect_schema` → `execute_query` / `execute_mutation`.

## Quirks
- **Times are ISO 8601 with the account's timezone offset** — not unix-seconds like the old REST API. Pull the TZ from `get_account` and build the offset; never assume UTC.
- **Default scheduling is `addToQueue`** (next open slot in the channel's schedule). Only override when the user asks for a specific time.
- **One post per channel** — to publish the same content to multiple platforms, pass multiple `channelId`s in a single `create_post` call (or create one post per channel if they need different copy).
- Buffer's free tier still caps scheduled posts per channel — fine for one-week campaigns, but watch it when onboarding multiple clients.

## Impact on the project workflow
- `src/scheduler/` is now a thin wrapper around MCP tool calls, not a REST client. No `buffer_client.py` with `requests` / `httpx` — the MCP server handles HTTP.
- `.env` no longer needs `BUFFER_ACCESS_TOKEN` or `BUFFER_PROFILE_IDS`. The token lives in the MCP server header config (`~/.claude.json`), and channel IDs are discovered at runtime via `list_channels`.
- The generator's platform recommendation (IG / X / LinkedIn / FB) must map to a real `channelId` from `list_channels` before scheduling. Add a small channel-name → channel-id resolver in `src/scheduler/`.
- Campaign data model: store `channelId`s per post (not profile IDs), and store the org ID on the campaign so multi-tenant routing works later.

## Computer Use fallback
If the MCP server ever breaks or Buffer restricts API access, fall back to Claude Computer Use driving publish.buffer.com directly. Don't do this first — it's 10x slower and flakier. See `docs/computer_use_fallback.md` (to be written).
