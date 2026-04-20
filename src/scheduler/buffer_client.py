"""
Buffer GraphQL client.

Uses the Buffer GraphQL API (https://api.bufferapp.com/graphql) with a bearer
token from BUFFER_API_KEY in .env.

Workflow:
  1. get_organization_id()  — call once, cache the result.
  2. list_channels()        — returns id/name/service per channel.
  3. create_post()          — schedules one post on one or more channels.
"""
from __future__ import annotations

import httpx

from src.config import settings

ENDPOINT = "https://api.buffer.com"


class BufferError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.buffer_api_key:
        raise BufferError("BUFFER_API_KEY not set in .env")
    return {"Authorization": f"Bearer {settings.buffer_api_key}"}


def _gql(query: str, variables: dict | None = None) -> dict:
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    with httpx.Client(timeout=30.0) as c:
        r = c.post(ENDPOINT, json=payload, headers=_headers())
        r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise BufferError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def get_organization_id() -> str:
    data = _gql("{ account { organizations { id } } }")
    return data["account"]["organizations"][0]["id"]


def list_channels(organization_id: str) -> list[dict]:
    """Returns list of {id, name, service} dicts."""
    q = """
    { account { organizations { id channels { id name service } } } }
    """
    data = _gql(q)
    for org in data["account"]["organizations"]:
        if org["id"] == organization_id:
            return org["channels"]
    return []


# Maps our platform strings to Buffer service names.
_PLATFORM_MAP = {
    "instagram": "instagram",
    "twitter": "twitter",
    "linkedin": "linkedin",
    "facebook": "facebook",
    "tiktok": "tiktok",
}


def resolve_channel_id(channels: list[dict], platform: str) -> str | None:
    """Return the first channel id whose service matches the platform string."""
    service = _PLATFORM_MAP.get(platform.lower())
    if not service:
        return None
    for ch in channels:
        if ch.get("service", "").lower() == service:
            return ch["id"]
    return None


def create_post(
    *,
    text: str,
    channel_id: str,
    due_at: str | None = None,
    image_url: str | None = None,
) -> dict:
    """
    Schedule a post on one channel. due_at is ISO 8601 with timezone offset.
    Omit to add to queue. Returns the created post dict.
    """
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id status dueAt }
        }
        ... on InvalidInputError { message }
        ... on LimitReachedError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError   { message }
        ... on RestProxyError    { message }
      }
    }
    """
    inp: dict = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "customScheduled" if due_at else "addToQueue",
    }
    if due_at:
        inp["dueAt"] = due_at
    if image_url:
        inp["assets"] = {"images": [{"url": image_url}]}

    data = _gql(mutation, {"input": inp})
    result = data["createPost"]
    if "post" not in result:
        raise BufferError(f"createPost failed: {result.get('message', result)}")
    return result["post"]
