"""Shared settings for EditKit."""
from __future__ import annotations

import os
from pathlib import Path

OUTPUT_DIR = Path(os.environ.get("EDITKIT_OUTPUT", Path(__file__).parent / "output"))
WHISPER_MODEL = os.environ.get("EDITKIT_WHISPER", "base")  # tiny|base|small|medium|large-v3
MODEL = os.environ.get("EDITKIT_MODEL", "claude-opus-4-8")
