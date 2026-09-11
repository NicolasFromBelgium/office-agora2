"""Thin SpaceXAI (xAI) chat client. Optional: works without a key."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from agora.settings import Settings

XAI_URL = "https://api.x.ai/v1/chat/completions"


def complete(settings: Settings, messages: list[dict[str, str]], timeout: int = 20) -> str:
    if not settings.xai_api_key:
        raise RuntimeError("XAI_API_KEY manquante")
    payload = json.dumps(
        {
            "model": settings.xai_model or "grok-4.6",
            "messages": messages,
            "temperature": 0.4,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        XAI_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.xai_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"xAI injoignable: {exc}") from exc
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("Réponse xAI vide")
    text = choices[0].get("message", {}).get("content") or ""
    return text.strip()
