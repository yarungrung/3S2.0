"""Gemini integration. Gemini only returns JSON weights."""

import json
from typing import Any

from backend.ai.prompt import SYSTEM_PROMPT
from backend.config import get_settings


DEFAULT_AI_RESULT: dict[str, Any] = {
    "reasoning": "我會依照你的需求調整權重，再交由 NetworkX 計算路線。",
    "walking_speed_multiplier": 1.0,
    "banned_vehicles": [],
    "weights": {
        "walking": 1.0,
        "taxi": 1.0,
        "mrt": 1.0,
        "bus": 1.0,
        "train": 1.0,
        "ubike": 1.0,
        "car": 1.0,
        "scooter": 1.0,
    },
}


def get_gemini_weights(user_input: str, weather: str, profile: str) -> dict[str, Any]:
    """Ask Gemini for JSON routing weights, falling back to safe defaults."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return DEFAULT_AI_RESULT.copy()
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        context = f"生理基礎: {profile}\n天氣: {weather}\n需求: {user_input}"
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=context,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return normalize_ai_result(json.loads(response.text))
    except Exception:
        return DEFAULT_AI_RESULT.copy()


def normalize_ai_result(result: dict[str, Any]) -> dict[str, Any]:
    """Ensure Gemini output has the expected routing JSON shape."""
    normalized = DEFAULT_AI_RESULT.copy()
    normalized.update({k: v for k, v in result.items() if k != "weights"})
    weights = DEFAULT_AI_RESULT["weights"].copy()
    weights.update(result.get("weights", {}))
    normalized["weights"] = weights
    normalized["banned_vehicles"] = result.get("banned_vehicles", [])
    return normalized
