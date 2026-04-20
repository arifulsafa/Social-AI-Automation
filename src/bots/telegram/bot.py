"""
Telegram bot — phone control surface.

Commands:
  /new <niche>    Generate a week of posts
  /review         Walk through drafts one-by-one
  /schedule       Push approved posts to Buffer
  /status         Show campaign summary
  /cancel         Abort current review

Free-text messages while reviewing a post are treated as edit instructions
(Claude rewrites the post).

Run: python -m src.bots.telegram.bot
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlmodel import select
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.api import campaigns as svc
from src.config import settings
from src.db.models import Campaign, Post, PostState, get_session, init_db
from src.scheduler.scheduler import schedule_campaign

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("tg-bot")


# ---------- access control ----------
def _allowed(update: Update) -> bool:
    allow = settings.telegram_allowed_user_id_set
    if not allow:
        return True  # wide-open mode — only for local dev
    return update.effective_user and update.effective_user.id in allow


# ---------- helpers ----------
def _keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{post_id}"),
                InlineKeyboardButton("🔁 Regenerate", callback_data=f"regen:{post_id}"),
            ],
            [
                InlineKeyboardButton("⏭ Skip", callback_data=f"skip:{post_id}"),
                InlineKeyboardButton("Next ➡️", callback_data=f"next:{post_id}"),
            ],
        ]
    )


def _escape(text: str) -> str:
    """Escape MarkdownV2 special characters in plain-text content."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _format_post(p: Post) -> str:
    when = p.scheduled_at.isoformat() if p.scheduled_at else "unscheduled"
    warning = f"\n⚠️ _{_escape(p.last_error)}_" if p.last_error else ""
    return (
        f"*Day {p.day_index + 1} — {_escape(p.platform)}*\n"
        f"_when:_ `{when}`{warning}\n\n"
        f"{_escape(p.caption)}\n\n"
        f"{_escape(p.hashtags)}"
    )


def _latest_campaign_for_chat(chat_id: int) -> Campaign | None:
    with get_session() as s:
        return s.exec(
            select(Campaign)
            .where(Campaign.telegram_chat_id == chat_id)
            .order_by(Campaign.id.desc())  # type: ignore
        ).first()


def _next_reviewable(campaign_id: int, after_day: int = -1) -> Post | None:
    with get_session() as s:
        return s.exec(
            select(Post)
            .where(
                Post.campaign_id == campaign_id,
                Post.day_index > after_day,
                Post.state.in_([PostState.DRAFT, PostState.PENDING_APPROVAL]),  # type: ignore
            )
            .order_by(Post.day_index)  # type: ignore
        ).first()


async def _send_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE, post: Post) -> None:
    ctx.user_data["reviewing_post_id"] = post.id
    kb = _keyboard(post.id)
    caption = _format_post(post)
    if post.image_path and Path(post.image_path).exists():
        with open(post.image_path, "rb") as fh:
            await update.effective_chat.send_photo(
                photo=InputFile(fh),
                caption=caption,
                parse_mode="MarkdownV2",
                reply_markup=kb,
            )
    else:
        await update.effective_chat.send_message(
            caption, parse_mode="MarkdownV2", reply_markup=kb
        )


# ---------- command handlers ----------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text(
        "Hey! I'm your social AI.\n\n"
        "• /new <niche>\n"
        "• /review\n"
        "• /schedule\n"
        "• /status"
    )


async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    niche = " ".join(ctx.args).strip()
    if not niche:
        await update.message.reply_text("Usage: /new vegan bakery in Austin")
        return

    await update.message.reply_text(f"🧠 Generating {settings.campaign_post_count} posts for: *{_escape(niche)}*", parse_mode="MarkdownV2")
    camp = svc.create_campaign(niche=niche, telegram_chat_id=update.effective_chat.id)
    svc.generate_drafts(camp.id)
    await update.message.reply_text("🎨 Rendering images (this takes ~1 min)...")
    svc.render_images(camp.id)
    await update.message.reply_text("✅ Drafts ready. Run /review to step through them.")


async def cmd_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    camp = _latest_campaign_for_chat(update.effective_chat.id)
    if camp is None:
        await update.message.reply_text("No campaigns yet. Try /new <niche>.")
        return
    post = _next_reviewable(camp.id)
    if post is None:
        await update.message.reply_text("Nothing left to review. /schedule when ready.")
        return
    await _send_post(update, ctx, post)


async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    camp = _latest_campaign_for_chat(update.effective_chat.id)
    if camp is None:
        await update.message.reply_text("No campaign to schedule.")
        return
    try:
        scheduled = schedule_campaign(camp.id)
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(f"❌ Scheduling failed: {e}")
        return
    await update.message.reply_text(f"📅 Scheduled {len(scheduled)} posts on Buffer.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    camp = _latest_campaign_for_chat(update.effective_chat.id)
    if camp is None:
        await update.message.reply_text("No campaigns yet.")
        return
    with get_session() as s:
        posts = s.exec(select(Post).where(Post.campaign_id == camp.id)).all()
    counts: dict[str, int] = {}
    for p in posts:
        counts[p.state] = counts.get(p.state, 0) + 1
    lines = [f"*{_escape(camp.niche)}* \\(id {camp.id}\\)"]
    for k, v in counts.items():
        lines.append(f"• {_escape(k)}: {v}")
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


# ---------- callback buttons ----------
async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    q = update.callback_query
    await q.answer()
    action, sid = q.data.split(":", 1)
    post_id = int(sid)

    if action == "approve":
        svc.approve(post_id)
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text("✅ Approved.")
        await _advance(update, ctx, post_id)
    elif action == "skip":
        with get_session() as s:
            post = s.get(Post, post_id)
            post.state = PostState.SKIPPED
            s.add(post)
            s.commit()
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text("⏭ Skipped.")
        await _advance(update, ctx, post_id)
    elif action == "next":
        await _advance(update, ctx, post_id)
    elif action == "regen":
        ctx.user_data["awaiting_edit_for"] = post_id
        await q.message.reply_text("✏️ Send me instructions (e.g. 'shorter, add a CTA').")


async def _advance(update: Update, ctx: ContextTypes.DEFAULT_TYPE, current_post_id: int) -> None:
    with get_session() as s:
        p = s.get(Post, current_post_id)
        campaign_id = p.campaign_id
        current_day = p.day_index
    nxt = _next_reviewable(campaign_id, after_day=current_day)
    if nxt is None:
        await update.effective_chat.send_message("🎉 All done. Run /schedule to push to Buffer.")
        return
    await _send_post(update, ctx, nxt)


# ---------- free-text -> edit ----------
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    pending = ctx.user_data.get("awaiting_edit_for")
    if not pending:
        await update.message.reply_text("Use /new, /review, /schedule, or /status.")
        return
    instruction = update.message.text
    await update.message.reply_text("🔁 Rewriting...")
    post = svc.apply_edit(pending, instruction)
    ctx.user_data["awaiting_edit_for"] = None
    await _send_post(update, ctx, post)


def main() -> None:
    init_db()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set in .env")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("review", cmd_review))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Telegram bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
