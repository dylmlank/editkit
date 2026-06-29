"""EditKit's capability layer for video editing — shared by the MCP server and
the standalone agent. Handlers shell out to ffmpeg/ffprobe and (for captions /
picking moments) faster-whisper. run_ffmpeg is the escape hatch for anything the
named tools don't cover. No live app — these operate on files.
"""
from __future__ import annotations

import json
import re
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


# --- Trendy-edit engine ------------------------------------------------------

def _duration(path: str):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=nk=1:nw=1", path], capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return None


def _sub_path(name: str) -> str:
    return _ff_path(_out(name))


def _ff_path(p: str) -> str:
    """Escape a path for use inside an ffmpeg filter (subtitles=...)."""
    return p.replace("\\", "/").replace(":", "\\:")


def auto_jumpcut(input: str, output: str, threshold_db: float = -30.0,
                 min_silence: float = 0.4) -> str:
    """Remove silent gaps (dead air, long pauses) for a tight, jump-cut edit."""
    if not Path(input).exists():
        return f"No such file: {input}"
    if not shutil.which("ffmpeg"):
        return "ffmpeg is not on PATH."
    dur = _duration(input)
    det = subprocess.run(["ffmpeg", "-hide_banner", "-i", input, "-af",
                         f"silencedetect=noise={threshold_db}dB:d={min_silence}",
                         "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", det.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", det.stderr)]
    if len(starts) > len(ends) and dur:
        ends.append(dur)
    silences = list(zip(starts, ends))
    keep, cur = [], 0.0
    for s, e in silences:
        if s > cur:
            keep.append((cur, s))
        cur = e
    if dur and dur > cur + 0.05:
        keep.append((cur, dur))
    if not keep:
        return "No speech detected to keep (or no silence found to cut)."
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)
    out = _out(output)
    r = _ff(["-i", input, "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
             "-af", f"aselect='{expr}',asetpts=N/SR/TB", out])
    if r != "ok":
        return r
    kept = sum(b - a for a, b in keep)
    saved = (dur - kept) if dur else 0
    return f"Jump-cut -> {out} ({len(keep)} kept spans, ~{saved:.1f}s of silence removed)."


def _ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{int(s):02d}.{int((s % 1) * 100):02d}"


def captions(input: str, output: str, max_words: int = 5, font_size: int = 64) -> str:
    """Burn animated word-by-word ('karaoke') captions — the trendy TikTok look."""
    if not Path(input).exists():
        return f"No such file: {input}"
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return "faster-whisper not installed (pip install faster-whisper)."
    model = WhisperModel(WHISPER_MODEL, device="auto", compute_type="int8")
    segments, _ = model.transcribe(input, word_timestamps=True)

    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Pop,Arial,{font_size},&H0000FFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,0,0,1,4,1,2,40,40,260,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for seg in segments:
        words = [w for w in (seg.words or []) if w.word.strip()]
        for i in range(0, len(words), max_words):
            grp = words[i:i + max_words]
            start, end = grp[0].start, grp[-1].end
            text = ""
            for w in grp:
                cs = max(1, int(round((w.end - w.start) * 100)))
                text += f"{{\\kf{cs}}}{w.word.strip()} "
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Pop,,0,0,0,,{text.strip()}")
    if not lines:
        return "No speech detected to caption."
    ass = _out("captions.ass")
    Path(ass).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")

    out = _out(output)
    r = _ff(["-i", input, "-vf", f"subtitles='{_ff_path(ass)}'", "-c:a", "copy", out])
    return f"Captioned -> {out}" if r == "ok" else r


def _detect_face_x(input: str):
    """Median horizontal face position (0..1) across sampled frames, or None."""
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(input)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, total // 20) if total else 30
    xs, i = [], 0
    while True:
        if not cap.grab():
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                w = frame.shape[1]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, 1.2, 5)
                if len(faces):
                    fx, _, fw, _ = max(faces, key=lambda f: f[2] * f[3])
                    xs.append((fx + fw / 2) / w)
        i += 1
    cap.release()
    if not xs:
        return None
    xs.sort()
    return xs[len(xs) // 2]


def reframe_vertical(input: str, output: str, face_x: float | None = None) -> str:
    """Crop to 9:16 keeping the speaker centered. face_x (0=left,1=right) overrides
    detection; if omitted, OpenCV finds the face, else falls back to center."""
    if not Path(input).exists():
        return f"No such file: {input}"
    detected = ""
    if face_x is None:
        face_x = _detect_face_x(input)
        detected = f" (auto face_x={face_x:.2f})" if face_x is not None else " (centered; no face found)"
    if face_x is None:
        face_x = 0.5
    face_x = max(0.0, min(1.0, float(face_x)))
    out = _out(output)
    vf = f"crop=ih*9/16:ih:(iw-ih*9/16)*{face_x:.3f}:0,scale=1080:1920"
    r = _ff(["-i", input, "-vf", vf, "-c:a", "aac", out])
    return f"Reframed 9:16 -> {out}{detected}" if r == "ok" else r


def normalize_audio(input: str, output: str) -> str:
    """Loudness-normalize to -14 LUFS (social-platform target) via EBU R128."""
    if not Path(input).exists():
        return f"No such file: {input}"
    out = _out(output)
    r = _ff(["-i", input, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "copy", out])
    return f"Normalized -> {out}" if r == "ok" else r


_HANDLERS = {
    "probe": probe, "transcribe": transcribe, "make_clip": make_clip,
    "speed": speed, "add_text": add_text, "concat": concat,
    "extract_audio": extract_audio, "run_ffmpeg": run_ffmpeg,
    "auto_jumpcut": auto_jumpcut, "captions": captions,
    "reframe_vertical": reframe_vertical, "normalize_audio": normalize_audio,
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
    {"name": "auto_jumpcut",
     "description": "Remove silent gaps / dead air for a tight jump-cut edit. Lower threshold_db (e.g. -35) cuts more aggressively.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "output": {"type": "string"},
         "threshold_db": {"type": "number"}, "min_silence": {"type": "number"}},
      "required": ["input", "output"]}},
    {"name": "captions",
     "description": "Burn animated word-by-word ('karaoke') captions — the trendy TikTok/Shorts look. Run on a (usually vertical) clip. max_words = words shown per line.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "output": {"type": "string"},
         "max_words": {"type": "integer"}, "font_size": {"type": "integer"}},
      "required": ["input", "output"]}},
    {"name": "reframe_vertical",
     "description": "Crop to 9:16 keeping the speaker centered (face-aware via OpenCV). Pass face_x 0..1 to override. Use instead of make_clip's plain center-crop when there's a person.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "output": {"type": "string"}, "face_x": {"type": "number"}},
      "required": ["input", "output"]}},
    {"name": "normalize_audio",
     "description": "Loudness-normalize to -14 LUFS (social target) via EBU R128 — do this as a final pass for consistent volume.",
     "input_schema": {"type": "object", "properties": {
         "input": {"type": "string"}, "output": {"type": "string"}}, "required": ["input", "output"]}},
]


def dispatch(name: str, arguments: dict) -> str:
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    try:
        return handler(**(arguments or {}))
    except Exception as e:
        return f"Error in {name}: {e}"
