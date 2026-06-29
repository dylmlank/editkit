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


@mcp.tool()
def auto_jumpcut(input: str, output: str, threshold_db: float = -30.0,
                 min_silence: float = 0.4) -> str:
    """Remove silent gaps / dead air for a tight jump-cut edit."""
    return T.auto_jumpcut(input, output, threshold_db, min_silence)


@mcp.tool()
def captions(input: str, output: str, max_words: int = 5, font_size: int = 64) -> str:
    """Burn animated word-by-word ('karaoke') captions — the trendy look."""
    return T.captions(input, output, max_words, font_size)


@mcp.tool()
def reframe_vertical(input: str, output: str, face_x: float = -1.0) -> str:
    """Crop to 9:16 keeping the speaker centered (face-aware). face_x<0 = auto-detect."""
    return T.reframe_vertical(input, output, None if face_x < 0 else face_x)


@mcp.tool()
def normalize_audio(input: str, output: str) -> str:
    """Loudness-normalize to -14 LUFS (social target) via EBU R128."""
    return T.normalize_audio(input, output)


@mcp.tool()
def add_music(input: str, music: str, output: str, music_db: float = -18.0,
              duck: bool = True) -> str:
    """Lay a background music bed under the video; duck=True ducks it under the voice."""
    return T.add_music(input, music, output, music_db, duck)


@mcp.tool()
def detect_beats(music: str) -> str:
    """Detect tempo + beat timestamps (seconds) so you can cut on the beat."""
    return T.detect_beats(music)


@mcp.tool()
def transition(input_a: str, input_b: str, output: str, kind: str = "fade",
               duration: float = 0.5) -> str:
    """Cross-fade clip A into clip B (fade|dissolve|wipeleft|slideup|circleopen...)."""
    return T.transition(input_a, input_b, output, kind, duration)


@mcp.tool()
def zoom_punch(input: str, output: str, zoom: float = 1.3) -> str:
    """Smooth Ken-Burns zoom-in across the clip (1.0 -> zoom) — trendy slow push."""
    return T.zoom_punch(input, output, zoom)


@mcp.tool()
def overlay(input: str, over: str, output: str, position: str = "top-right",
            scale: float = 0.25, start: float = -1.0, end: float = -1.0) -> str:
    """Overlay a logo / picture-in-picture / b-roll. start/end<0 = always shown."""
    s = None if start < 0 else start
    e = None if end < 0 else end
    return T.overlay(input, over, output, position, scale, s, e)


@mcp.tool()
def color_grade(input: str, output: str, preset: str = "", saturation: float = 1.0,
                contrast: float = 1.0, brightness: float = 0.0, gamma: float = 1.0) -> str:
    """Color-grade: preset warm|cool|cinematic|vivid|bw|vintage + manual eq."""
    return T.color_grade(input, output, preset, saturation, contrast, brightness, gamma)


@mcp.tool()
def thumbnail(input: str, output: str = "thumbnail.jpg", text: str = "",
              at: str = "00:00:01", font_size: int = 90) -> str:
    """Grab a frame + optional big hook headline for a YouTube/Shorts cover."""
    return T.thumbnail(input, output, text, at, font_size)


@mcp.tool()
def export_formats(input: str, base_name: str = "export", formats: list | None = None) -> str:
    """Render to multiple aspect ratios at once: 9x16, 1x1, 16x9."""
    return T.export_formats(input, base_name, formats)


if __name__ == "__main__":
    mcp.run()
