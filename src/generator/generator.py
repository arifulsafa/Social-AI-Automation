import json
from datetime import date
from pathlib import Path

from anthropic import Anthropic
from pydantic import BaseModel, Field, field_validator

from src.config import settings

PROMPT_PATH = Path(__file__).parent / "prompts" / "week_of_posts.md"

VALID_PLATFORMS = {"instagram", "twitter", "linkedin", "facebook", "tiktok"}


class DraftPost(BaseModel):
    day_index: int = Field(ge=0, le=6)
    platform: str
    post_type: str
    caption: str
    hashtags: list[str]
    image_prompt: str
    suggested_time_local: str

    @field_validator("platform")
    @classmethod
    def _platform_ok(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_PLATFORMS:
            raise ValueError(f"platform must be one of {VALID_PLATFORMS}")
        return v


class WeekOfPosts(BaseModel):
    posts: list[DraftPost]
    expected_count: int = 7

    @field_validator("posts")
    @classmethod
    def _correct_count(cls, v: list[DraftPost]) -> list[DraftPost]:
        return v  # count validated in generate_week after construction

    def validate_count(self, n: int) -> None:
        if len(self.posts) != n:
            raise ValueError(f"expected {n} posts, got {len(self.posts)}")
        days = sorted(p.day_index for p in self.posts)
        if days != list(range(n)):
            raise ValueError(f"day_index must cover 0..{n-1}, got {days}")


def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
    return Anthropic(api_key=settings.anthropic_api_key)


def generate_week(
    niche: str,
    tone: str = "friendly-professional",
    week_start: date | None = None,
    post_count: int | None = None,
    platforms: list[str] | None = None,
) -> WeekOfPosts:
    week_start = week_start or date.today()
    post_count = post_count or settings.campaign_post_count
    platforms = platforms or settings.campaign_platform_list

    prompt = PROMPT_PATH.read_text().format(
        niche=niche,
        tone=tone,
        week_start=week_start.isoformat(),
        post_count=post_count,
        post_count_minus_1=post_count - 1,
        platforms=", ".join(platforms),
    )

    msg = _client().messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(raw)
    result = WeekOfPosts.model_validate(data)
    result.validate_count(post_count)
    return result


def regenerate_post(niche: str, tone: str, original: DraftPost, instruction: str) -> DraftPost:
    """Rewrite one post based on a free-text instruction from the user (via Telegram)."""
    user_msg = (
        f"Original post for a {niche} business (tone: {tone}):\n"
        f"{original.model_dump_json(indent=2)}\n\n"
        f"User edit instruction: {instruction}\n\n"
        f"Return ONLY a JSON object matching the same schema as the original "
        f"(day_index, platform, post_type, caption, hashtags, image_prompt, "
        f"suggested_time_local). Keep day_index and platform unless the user "
        f"explicitly asked to change them. No prose, no code fences."
    )
    msg = _client().messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return DraftPost.model_validate(json.loads(raw))
