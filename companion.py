r"""EditKit companion — a small always-handy prompt window for editing video.

There's no host app to embed into (EditKit is ffmpeg under the hood), so this is the
next best thing: a floating window. Pick a video, type what you want ("cut the dead
air, reframe vertical, add karaoke captions, then a cinematic grade"), hit Generate,
and Claude runs EditKit's tools on it. Outputs land in editkit/output/.

Run it:
    uv run --python 3.12 --with anthropic --with faster-whisper python companion.py

API key: put your OpenRouter key in a file `E:\editkit\.env` as
    OPENROUTER_API_KEY=sk-or-v1-...
and choose a model with EDITKIT_MODEL. No key yet? The window still opens and
shows you exactly where to add one.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
from pathlib import Path


def _app_dir() -> Path:
    """Folder the program lives in (next to the .exe when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# Load .env (next to the program) into the environment before anything reads the key.
def _load_env():
    env = _app_dir() / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

import tkinter as tk  # noqa: E402
from tkinter import filedialog, scrolledtext  # noqa: E402

from config import OUTPUT_DIR  # noqa: E402
from core import TOOLS, dispatch  # noqa: E402
from core.llm import make_client, run_loop  # noqa: E402

SYSTEM = (
    "You are EditKit, a video-editing assistant. You operate on local files with "
    "ffmpeg-based tools (cut, reframe 9:16, jump-cut silence, karaoke captions, "
    "speed, transitions, zoom punches, overlays, color grade, music bed + ducking, "
    "thumbnails, multi-format export). The user's input video path is given in the "
    "prompt; pass it as `input`. Chain tools to reach the result; outputs are written "
    "to the output folder. Keep replies short; act with the tools."
)


def run_agent(prompt: str, log) -> None:
    client = make_client()
    messages = [{"role": "user", "content": prompt}]
    run_loop(client, TOOLS, lambda n, a: dispatch(n, a),
             SYSTEM, messages, log, max_tokens=4096)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        root.title("EditKit")
        root.geometry("560x520")
        root.attributes("-topmost", True)

        self.have_key = bool(os.environ.get("OPENROUTER_API_KEY")
                             or os.environ.get("ANTHROPIC_API_KEY"))
        if not self.have_key:
            banner = tk.Label(
                root, bg="#7a1f1f", fg="white", anchor="w", justify="left",
                text=(" No OpenRouter key. Add OPENROUTER_API_KEY=sk-or-v1-... to "
                      "E:\\editkit\\.env  (and set EDITKIT_MODEL) and reopen."))
            banner.pack(fill="x")

        top = tk.Frame(root)
        top.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(top, text="Video:").pack(side="left")
        self.video = tk.Entry(top)
        self.video.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(top, text="Browse…", command=self.browse).pack(side="left")

        tk.Label(root, text="Prompt:", anchor="w").pack(fill="x", padx=8, pady=(8, 0))
        self.prompt = tk.Text(root, height=4, wrap="word")
        self.prompt.pack(fill="x", padx=8)
        self.prompt.insert("1.0", "cut the silence, reframe to 9:16, add karaoke captions")

        self.go = tk.Button(root, text="Generate", command=self.generate)
        self.go.pack(fill="x", padx=8, pady=6)

        self.out = scrolledtext.ScrolledText(root, height=16, state="disabled", wrap="word")
        self.out.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.root.after(100, self._drain)

    def browse(self):
        path = filedialog.askopenfilename(
            title="Choose a video",
            filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm"), ("All", "*.*")])
        if path:
            self.video.delete(0, "end")
            self.video.insert(0, path)

    def log(self, msg: str):
        self.q.put(msg)

    def _drain(self):
        while not self.q.empty():
            msg = self.q.get()
            self.out.configure(state="normal")
            self.out.insert("end", msg + "\n")
            self.out.see("end")
            self.out.configure(state="disabled")
            if msg == "__DONE__":
                self.go.configure(state="normal", text="Generate")
        self.root.after(100, self._drain)

    def generate(self):
        if not self.have_key:
            self.log("Add OPENROUTER_API_KEY to E:\\editkit\\.env first.")
            return
        video = self.video.get().strip()
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            self.log("Type a prompt first.")
            return
        full = prompt if not video else f"The input video is at: {video}\n\n{prompt}"
        self.go.configure(state="disabled", text="Working…")
        self.log(f"> {prompt}")

        def worker():
            try:
                run_agent(full, self.log)
            except Exception as e:
                self.log(f"Error: {e}")
            finally:
                self.log(f"(outputs in {OUTPUT_DIR})")
                self.log("__DONE__")

        threading.Thread(target=worker, daemon=True).start()


def _selftest():
    """Verify a frozen build loads, then exit. Run as: EditKit.exe --selftest"""
    import json
    result = {"app": "EditKit", "frozen": bool(getattr(sys, "frozen", False))}
    try:
        import openai
        openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key="selftest")
        result["openai"] = openai.__version__
    except Exception as e:
        result["openai"] = f"FAIL: {e}"
    try:
        root = tk.Tk()
        App(root)
        root.update()
        root.destroy()
        result["ui"] = "ok"
    except Exception as e:
        result["ui"] = f"FAIL: {e}"
    (_app_dir() / "selftest.json").write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps(result))


def main():
    if "--selftest" in sys.argv:
        _selftest()
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
