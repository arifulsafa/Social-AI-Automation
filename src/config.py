from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-7"

    higgsfield_key_id: str = ""
    higgsfield_key_secret: str = ""

    buffer_api_key: str = ""

    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""

    # Campaign defaults — override in .env
    campaign_post_count: int = 7
    campaign_platforms: str = "instagram,twitter,linkedin,facebook"

    @property
    def campaign_platform_list(self) -> list[str]:
        return [p.strip().lower() for p in self.campaign_platforms.split(",") if p.strip()]

    database_url: str = "sqlite:///./social_ai.db"
    image_dir: Path = Path("./data/images")
    log_level: str = "INFO"

    @property
    def telegram_allowed_user_id_set(self) -> set[int]:
        return {
            int(x.strip())
            for x in self.telegram_allowed_user_ids.split(",")
            if x.strip()
        }


settings = Settings()
settings.image_dir.mkdir(parents=True, exist_ok=True)
