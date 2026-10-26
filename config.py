"""Shared settings for EditKit."""
from __future__ import annotations

import os
from pathlib import Path

OUTPUT_DIR = Path(os.environ.get("EDITKIT_OUTPUT", Path(__file__).parent / "output"))
WHISPER_MODEL = os.environ.get("EDITKIT_WHISPER", "base")  # tiny|base|small|medium|large-v3
# Generation goes through OpenRouter's OpenAI-compatible endpoint, so any
# OpenRouter model works — set the slug in .env (e.g. openai/gpt-oss-120b:free).
BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.environ.get("EDITKIT_MODEL", "")
