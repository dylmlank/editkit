"""EditKit standalone agent — point Claude at a video and ask for edits or trendy
clips; it orchestrates the same ffmpeg/whisper tools the MCP server exposes.

    set ANTHROPIC_API_KEY=...
    python agent.py "turn C:/clips/stream.mp4 into three 30s vertical TikToks with captions"

Anthropic SDK manual tool-use loop, claude-opus-4-8, adaptive thinking.
"""
from __future__ import annotations

import sys

import anthropic

from config import MODEL, OUTPUT_DIR
from core import TOOLS, dispatch

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


def run(client, user_text, history):
    history.append({"role": "user", "content": user_text})
    while True:
        resp = client.messages.create(
            model=MODEL, max_tokens=8192, thinking={"type": "adaptive"},
            system=SYSTEM, tools=TOOLS, messages=history,
        )
        history.append({"role": "assistant", "content": resp.content})
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                print(f"\n{block.text.strip()}\n")
        if resp.stop_reason != "tool_use":
            return history
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = dispatch(block.name, block.input)
                preview = out if len(out) < 240 else out[:240] + "..."
                print(f"  · {block.name} -> {preview}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        history.append({"role": "user", "content": results})


def main() -> int:
    client = anthropic.Anthropic()
    history: list = []
    if len(sys.argv) > 1:
        run(client, " ".join(sys.argv[1:]), history)
        return 0
    print("EditKit agent — describe the edit (Ctrl+C to quit).")
    try:
        while True:
            text = input("\n> ").strip()
            if text:
                run(client, text, history)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
