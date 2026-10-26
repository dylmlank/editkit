r"""EditKit standalone agent — point a model at a video and ask for edits or trendy
clips; it orchestrates the same ffmpeg/whisper tools the MCP server exposes.

    # in E:\editkit\.env (or the environment):
    #   OPENROUTER_API_KEY=sk-or-v1-...
    #   EDITKIT_MODEL=openai/gpt-oss-120b:free      (any tool-capable OpenRouter model)
    python agent.py "turn C:/clips/stream.mp4 into three 30s vertical TikToks with captions"

Generation runs through OpenRouter's OpenAI-compatible API (core.llm).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env() -> None:
    env = Path(__file__).parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

from config import OUTPUT_DIR  # noqa: E402
from core import TOOLS, dispatch  # noqa: E402
from core.llm import make_client, run_loop  # noqa: E402

SYSTEM = (
    "You are EditKit, a video-editing assistant. You operate on local files using "
    "ffmpeg tools and faster-whisper. Workflow for 'trendy clips': probe the video, "
    "transcribe it, read the timestamped transcript, pick the most engaging/funny/"
    "surprising moments, then make_clip each one (vertical=True for TikTok/Shorts, "
    "passing the .srt to burn captions). For general edits use speed, add_text, "
    "concat, extract_audio, or run_ffmpeg for anything custom. Outputs land in "
    f"{OUTPUT_DIR}. Confirm the input path exists (probe) before heavy work. Keep "
    "prose short; act with tools."
)


def main() -> int:
    client = make_client()
    history: list = []

    def drive(text: str) -> None:
        history.append({"role": "user", "content": text})
        run_loop(client, TOOLS, lambda n, a: dispatch(n, a),
                 SYSTEM, history, print, max_tokens=8192)

    if len(sys.argv) > 1:
        drive(" ".join(sys.argv[1:]))
        return 0
    print("EditKit agent — describe the edit (Ctrl+C to quit).")
    try:
        while True:
            text = input("\n> ").strip()
            if text:
                drive(text)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
