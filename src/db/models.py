from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel, create_engine, Session

from src.config import settings


class PostState(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"
    SKIPPED = "skipped"


class Campaign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    niche: str
    tone: str = "friendly-professional"
    telegram_chat_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id", index=True)
    day_index: int  # 0..6
    platform: str  # instagram | twitter | linkedin | facebook
    caption: str
    hashtags: str
    image_prompt: str
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    buffer_update_id: Optional[str] = None
    state: PostState = Field(default=PostState.DRAFT)
    last_error: Optional[str] = None


engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
