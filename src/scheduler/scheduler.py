from datetime import timezone
from pathlib import Path

from sqlmodel import select

from src.db.models import Post, PostState, get_session
from src.scheduler.buffer_client import (
    create_post,
    get_organization_id,
    list_channels,
    resolve_channel_id,
)

# Cached per process — org id and channels don't change between posts.
_org_id: str | None = None
_channels: list[dict] | None = None


def _ensure_channels() -> list[dict]:
    global _org_id, _channels
    if _channels is None:
        _org_id = get_organization_id()
        _channels = list_channels(_org_id)
    return _channels


def schedule_post(post_id: int) -> Post:
    with get_session() as s:
        post = s.get(Post, post_id)
        if post is None:
            raise ValueError(f"Post {post_id} not found")
        if post.state != PostState.PENDING_APPROVAL:
            raise ValueError(f"Post {post_id} is in state {post.state}, expected pending_approval")

        channels = _ensure_channels()
        channel_id = resolve_channel_id(channels, post.platform)
        if not channel_id:
            raise ValueError(
                f"No Buffer channel found for platform '{post.platform}'. "
                f"Available: {[c['service'] for c in channels]}"
            )

        text = f"{post.caption}\n\n{post.hashtags}".strip()

        due_at: str | None = None
        if post.scheduled_at is not None:
            # Ensure UTC offset is explicit so Buffer doesn't misread the time.
            dt = post.scheduled_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            due_at = dt.isoformat()

        created = create_post(
            text=text,
            channel_id=channel_id,
            due_at=due_at,
            image_url=post.image_url,
        )
        post.buffer_update_id = created["id"]
        post.state = PostState.SCHEDULED
        s.add(post)
        s.commit()
        s.refresh(post)
        return post


def schedule_campaign(campaign_id: int) -> list[Post]:
    scheduled = []
    with get_session() as s:
        rows = s.exec(
            select(Post).where(
                Post.campaign_id == campaign_id,
                Post.state == PostState.PENDING_APPROVAL,
            )
        ).all()
    for p in rows:
        scheduled.append(schedule_post(p.id))
    return scheduled
