"""
Campaign service — the business logic shared between the HTTP API and the Telegram bot.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import select

from src.db.models import Campaign, Post, PostState, get_session
from src.generator.generator import generate_week, regenerate_post, DraftPost
from src.images.pollinations import generate_image


def create_campaign(
    *, niche: str, tone: str = "friendly-professional", telegram_chat_id: Optional[int] = None
) -> Campaign:
    with get_session() as s:
        c = Campaign(niche=niche, tone=tone, telegram_chat_id=telegram_chat_id)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def generate_drafts(campaign_id: int, *, week_start: Optional[date] = None) -> list[Post]:
    with get_session() as s:
        camp = s.get(Campaign, campaign_id)
        if camp is None:
            raise ValueError(f"Campaign {campaign_id} not found")

    week = generate_week(niche=camp.niche, tone=camp.tone, week_start=week_start)

    saved: list[Post] = []
    with get_session() as s:
        for d in week.posts:
            post = Post(
                campaign_id=campaign_id,
                day_index=d.day_index,
                platform=d.platform,
                caption=d.caption,
                hashtags=" ".join(f"#{h.lstrip('#')}" for h in d.hashtags),
                image_prompt=d.image_prompt,
                scheduled_at=_parse_iso(d.suggested_time_local),
                state=PostState.DRAFT,
            )
            s.add(post)
            saved.append(post)
        s.commit()
        for p in saved:
            s.refresh(p)
    return saved


def render_images(campaign_id: int) -> list[Post]:
    updated: list[Post] = []
    with get_session() as s:
        rows = s.exec(
            select(Post).where(Post.campaign_id == campaign_id, Post.image_path.is_(None))  # type: ignore
        ).all()
    for p in rows:
        try:
            path, image_url = generate_image(p.image_prompt)
            with get_session() as s:
                fresh = s.get(Post, p.id)
                fresh.image_path = str(path)
                fresh.image_url = image_url
                fresh.state = PostState.PENDING_APPROVAL
                s.add(fresh)
                s.commit()
                s.refresh(fresh)
                updated.append(fresh)
        except Exception as e:  # noqa: BLE001
            with get_session() as s:
                fresh = s.get(Post, p.id)
                # Image failed but the post is still reviewable/schedulable as text-only.
                fresh.state = PostState.PENDING_APPROVAL
                fresh.last_error = f"image: {e}"
                s.add(fresh)
                s.commit()
    return updated


def apply_edit(post_id: int, instruction: str) -> Post:
    with get_session() as s:
        post = s.get(Post, post_id)
        camp = s.get(Campaign, post.campaign_id)
    draft = DraftPost(
        day_index=post.day_index,
        platform=post.platform,
        post_type="(edit)",
        caption=post.caption,
        hashtags=post.hashtags.split(),
        image_prompt=post.image_prompt,
        suggested_time_local=(post.scheduled_at or datetime.utcnow()).isoformat(),
    )
    edited = regenerate_post(niche=camp.niche, tone=camp.tone, original=draft, instruction=instruction)
    with get_session() as s:
        fresh = s.get(Post, post_id)
        fresh.caption = edited.caption
        fresh.hashtags = " ".join(f"#{h.lstrip('#')}" for h in edited.hashtags)
        fresh.image_prompt = edited.image_prompt
        s.add(fresh)
        s.commit()
        s.refresh(fresh)
        return fresh


def approve(post_id: int) -> Post:
    with get_session() as s:
        post = s.get(Post, post_id)
        post.state = PostState.PENDING_APPROVAL
        s.add(post)
        s.commit()
        s.refresh(post)
        return post


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
