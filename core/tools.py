"""EditKit's capability layer for video editing — shared by the MCP server and
the standalone agent. Handlers shell out to ffmpeg/ffprobe and (for captions /
picking moments) faster-whisper. run_ffmpeg is the escape hatch for anything the
named tools don't cover. No live app — these operate on files.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from config import OUTPUT_DIR, WHISPER_MODEL


def _ff(args: list[str]) -> str:
    if not shutil.which("ffmpeg"):
        return "ffmpeg is not on PATH. Install ffmpeg first."
    try:
        p = subprocess.run(["ffmpeg", "-y", "-hide_banner", *args],
                           capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        return "ffmpeg timed out."
    if p.returncode != 0:
        return "ffmpeg error:\n" + (p.stderr[-1500:] if p.stderr else "(no output)")
    return "ok"


def _out(name: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(Path(OUTPUT_DIR) / name)


def probe(input: str) -> str:
    if not shutil.which("ffprobe"):
        return "ffprobe is not on PATH."
    if not Path(input).exists():
        return f"No such file: {input}"
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                       "-show_format", "-show_streams", input],
                      capture_output=True, text=True)
    try:
        d = json.loads(p.stdout)
    except json.JSONDecodeError:
        return p.stderr[-800:] or "probe failed"
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    fmt = d.get("format", {})
    return (f"duration={fmt.get('duration')}s size={fmt.get('size')}B "
            f"video={v.get('width')}x{v.get('height')} fps={v.get('r_frame_rate')} "
            f"vcodec={v.get('codec_name')}")


def transcribe(input: str, srt_name: str = "transcript.srt") -> str:
    if not Path(input).exists():
        return f"No such file: {input}"
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return "faster-whisper not installed (pip install faster-whisper) — needed for transcription/captions."
    model = WhisperModel(WHISPER_MODEL, device="auto", compute_type="int8")
    segments, _ = model.transcribe(input, word_timestamps=False)

    def ts(t):
        h, r = divmod(t, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s%1)*1000):03d}"

    lines, plain = [], []
    for i, seg in enumerate(segments, 1):
        lines.append(f"{i}\n{ts(seg.start)} --> {ts(seg.end)}\n{seg.text.strip()}\n")
        plain.append(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text.strip()}")
    srt_path = _out(srt_name)
    Path(srt_path).write_text("\n".join(lines), encoding="utf-8")
    body = "\n".join(plain)
    head = body if len(body) < 4000 else body[:4000] + "\n...(truncated; full SRT on disk)"
    return f"Saved SRT -> {srt_path}\nTranscript with timestamps:\n{head}"


def make_clip(input: str, start: str, end: str, output: str,
              vertical: bool = True, srt: str | None = None) -> str:
    """Cut [start,end] (HH:MM:SS or seconds); vertical=9:16; srt to burn captions."""
    if not Path(input).exists():
        return f"No such file: {input}"
    out = _out(output)
    filters = []
    if vertical:
        filters.append("crop=ih*9/16:ih,scale=1080:1920")
    if srt and Path(srt).exists():
        esc = srt.replace("\\", "/").replace(":", "\\:")
        filters.append(f"subtitles='{esc}':force_style='FontSize=18,Outline=2'")
    args = ["-ss", str(start), "-to", str(end), "-i", input]
    if filters:
        args += ["-vf", ",".join(filters)]
    args += ["-c:a", "aac", out]
    r = _ff(args)
    return f"Clip -> {out}" if r == "ok" else r


def speed(input: str, output: str, factor: float = 1.5) -> str:
    """Change playback speed (factor>1 faster). Trendy speed-ramp staple."""
    if not Path(input).exists():
        return f"No such file: {input}"
    out = _out(output)
    a = max(0.5, min(2.0, float(factor)))  # atempo clamps; chain for extremes
    r = _ff(["-i", input, "-filter_complex",
             f"[0:v]setpts=PTS/{factor}[v];[0:a]atempo={a}[a]",
             "-map", "[v]", "-map", "[a]", out])
    return f"Speed x{factor} -> {out}" if r == "ok" else r


def add_text(input: str, output: str, text: str, size: int = 48,
             y: str = "h-th-80") -> str:
    """Burn a centered text overlay (captions/titles)."""
    if not Path(input).exists():
        return f"No such file: {input}"
    out = _out(output)
    esc = text.replace("'", "’").replace(":", "\\:")
    r = _ff(["-i", input, "-vf",
             f"drawtext=text='{esc}':fontcolor=white:fontsize={size}:borderw=3:"
             f"bordercolor=black:x=(w-text_w)/2:y={y}", "-c:a", "copy", out])
    return f"Text overlay -> {out}" if r == "ok" else r


def concat(inputs: list[str], output: str) -> str:
    """Join clips end to end (must share codec/size; re-encode if unsure)."""
    missing = [p for p in inputs if not Path(p).exists()]
    if missing:
        return f"Missing files: {missing}"
    out = _out(output)
    listfile = _out("_concat.txt")
    Path(listfile).write_text("".join(f"file '{Path(p).resolve().as_posix()}'\n"
                                       for p in inputs), encoding="utf-8")
    r = _ff(["-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out])
    if r != "ok":  # fall back to re-encode if stream copy fails
        r = _ff(["-f", "concat", "-safe", "0", "-i", listfile, out])
    return f"Concatenated -> {out}" if r == "ok" else r


def extract_audio(input: str, output: str = "audio.wav") -> str:
    if not Path(input).exists():
        return f"No such file: {input}"
    out = _out(output)
    r = _ff(["-i", input, "-vn", out])
    return f"Audio -> {out}" if r == "ok" else r


def run_ffmpeg(args: list[str]) -> str:
    """Run an arbitrary ffmpeg command. Pass args as a list (no leading 'ffmpeg').
    Outputs to absolute paths you choose. The escape hatch for custom edits."""
    return _ff(list(args))


_HANDLERS = {
    "probe": probe, "transcribe": transcribe, "make_clip": make_clip,
    "speed": speed, "add_text": add_text, "concat": concat,
    "extract_audio": extract_audio, "run_ffmpeg": run_ffmpeg,
}

TOOLS = [
    {"name": "probe", "description": "Inspect a video: duration, resolution, fps, codec.",
     "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]}},
    {"name": "transcribe",
     "description": "Transcribe a video to an SRT and return timestamped text. Read this to pick the punchy moments for trendy clips, then call make_clip.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "srt_name": {"type": "string"}}, "required": ["input"]}},
    {"name": "make_clip",
     "description": "Cut a segment to output/. start/end are HH:MM:SS or seconds. vertical=True crops to 9:16 for TikTok/Shorts. Pass srt (an .srt path) to burn captions.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"},
         "output": {"type": "string"}, "vertical": {"type": "boolean"}, "srt": {"type": "string"}},
      "required": ["input", "start", "end", "output"]}},
    {"name": "speed", "description": "Change clip speed (factor>1 faster) — a trendy speed-ramp staple.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "output": {"type": "string"}, "factor": {"type": "number"}},
      "required": ["input", "output"]}},
    {"name": "add_text", "description": "Burn a centered text overlay (title/caption).",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "output": {"type": "string"}, "text": {"type": "string"},
         "size": {"type": "integer"}}, "required": ["input", "output", "text"]}},
    {"name": "concat", "description": "Join clips end to end.",
     "input_schema": {"type": "object", "properties": {
         "inputs": {"type": "array", "items": {"type": "string"}}, "output": {"type": "string"}},
      "required": ["inputs", "output"]}},
    {"name": "extract_audio", "description": "Extract the audio track to a file.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "output": {"type": "string"}}, "required": ["input"]}},
    {"name": "run_ffmpeg",
     "description": "Run an arbitrary ffmpeg command (args as a list, no leading 'ffmpeg'). Escape hatch for filters/edits the other tools don't cover.",
     "input_schema": {"type": "object", "properties": {
         "args": {"type": "array", "items": {"type": "string"}}}, "required": ["args"]}},
]


def dispatch(name: str, arguments: dict) -> str:
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    try:
        return handler(**(arguments or {}))
    except Exception as e:
        return f"Error in {name}: {e}"
