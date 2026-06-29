# EditKit

Claude-powered **video editing** — edit your videos and spin up trendy short-form
clips by talking to Claude. Same two-front-end design as your other kits:

- **MCP server** (`mcp_server.py`) — chat in **Claude Desktop**.
- **Standalone agent** (`agent.py`) — terminal agent via the Anthropic API.

Both drive the same ffmpeg/whisper tool layer over your local video files.

## What Claude can do

- **probe** — read a video's duration/resolution/fps
- **transcribe** — whisper → SRT + timestamped text (Claude reads this to *pick the
  punchy moments* for trendy clips)
- **make_clip** — cut a segment, auto-crop to **9:16** for TikTok/Shorts, optionally
  **burn captions** from the SRT
- **speed / add_text / concat / extract_audio** — speed ramps, titles, joins
- **run_ffmpeg** — the escape hatch: any ffmpeg command for custom edits

So *"turn stream.mp4 into three 30-second vertical TikToks with captions"* becomes:
probe → transcribe → Claude chooses the best moments → make_clip ×3.

The "trendy" judgment is Claude's — it reads the transcript and selects the
funny/surprising/quotable beats, rather than a fixed heuristic.

## Setup

**1. Install ffmpeg** (and ffprobe) on PATH — e.g. `winget install Gyan.FFmpeg`.

**2. Install Python deps** — `pip install -r requirements.txt`
(`anthropic`, `mcp`, `faster-whisper`; first transcription downloads the whisper model).

**3a. Claude Desktop (MCP)** — add to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
"editkit": {
  "command": "C:\\Users\\dylan\\.local\\bin\\uv.exe",
  "args": ["run", "--python", "3.12", "--with", "mcp", "--with", "faster-whisper",
           "python", "E:\\editkit\\mcp_server.py"]
}
```

**3b. Terminal agent**
```bash
set ANTHROPIC_API_KEY=sk-ant-...
uv run --python 3.12 --with anthropic --with faster-whisper python agent.py "make 3 trendy vertical clips from C:/clips/stream.mp4 with captions"
```

Outputs land in `./output/`.

## Layout

| Path | What it is |
| --- | --- |
| `core/tools.py` | capability layer (ffmpeg/whisper + run_ffmpeg) |
| `mcp_server.py` | FastMCP server for Claude Desktop |
| `agent.py` | standalone Anthropic-API agent |
| `config.py` | output dir + whisper size + model |

Replaces the old `vlogkit` + `autoclip` split with one Claude-driven editor.
