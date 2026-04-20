from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.api import campaigns as svc
from src.db.models import init_db
from src.scheduler.scheduler import schedule_campaign

app = FastAPI(title="Social AI Automation")


@app.on_event("startup")
def _startup() -> None:
    init_db()


class NewCampaignIn(BaseModel):
    niche: str
    tone: str = "friendly-professional"


@app.post("/campaigns")
def new_campaign(body: NewCampaignIn):
    c = svc.create_campaign(niche=body.niche, tone=body.tone)
    drafts = svc.generate_drafts(c.id)
    rendered = svc.render_images(c.id)
    return {"campaign_id": c.id, "drafts": len(drafts), "rendered": len(rendered)}


@app.post("/campaigns/{campaign_id}/schedule")
def schedule(campaign_id: int):
    try:
        scheduled = schedule_campaign(campaign_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"scheduled": [p.id for p in scheduled]}
