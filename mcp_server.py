"""EditKit MCP server — video editing tools for Claude Desktop. Each tool wraps a
core.tools handler (shared with agent.py).

claude_desktop_config.json:

    "editkit": {
      "command": "C:\\\\Users\\\\dylan\\\\.local\\\\bin\\\\uv.exe",
      "args": ["run", "--python", "3.12", "--with", "mcp",
               "python", "E:\\\\editkit\\\\mcp_server.py"]
    }

Needs ffmpeg/ffprobe on PATH; transcribe also needs faster-whisper.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import core.tools as T

mcp = FastMCP("editkit")


@mcp.tool()
def probe(input: str) -> str:
    """Inspect a video: duration, resolution, fps, codec."""
    return T.probe(input)


@mcp.tool()
def transcribe(input: str, srt_name: str = "transcript.srt") -> str:
    """Transcribe to SRT and return timestamped text (read it to pick clip moments)."""
    return T.transcribe(input, srt_name)


@mcp.tool()
def make_clip(input: str, start: str, end: str, output: str,
              vertical: bool = True, srt: str = "") -> str:
    """Cut a segment to output/. vertical=9:16; srt path burns captions."""
    return T.make_clip(input, start, end, output, vertical, srt or None)


@mcp.tool()
def speed(input: str, output: str, factor: float = 1.5) -> str:
    """Change clip speed (factor>1 faster)."""
    return T.speed(input, output, factor)


@mcp.tool()
def add_text(input: str, output: str, text: str, size: int = 48) -> str:
    """Burn a centered text overlay (title/caption)."""
    return T.add_text(input, output, text, size)


@mcp.tool()
def concat(inputs: list, output: str) -> str:
    """Join clips end to end."""
    return T.concat(inputs, output)


@mcp.tool()
def extract_audio(input: str, output: str = "audio.wav") -> str:
    """Extract the audio track to a file."""
    return T.extract_audio(input, output)


@mcp.tool()
def run_ffmpeg(args: list) -> str:
    """Run an arbitrary ffmpeg command (args list, no leading 'ffmpeg')."""
    return T.run_ffmpeg(args)


if __name__ == "__main__":
    mcp.run()
