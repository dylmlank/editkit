"""One command from raw clip to platform-ready vertical short — no LLM needed.

    python shorts.py clip.mp4
    python shorts.py clip.mp4 --music beat.mp3 --grade cinematic -o gym_day1.mp4

Runs make_short: jump-cut silences -> face-aware 9:16 -> karaoke captions ->
optional grade + ducked music -> -14 LUFS. Output lands in ./output/.
"""
from __future__ import annotations

import argparse

import core.tools as T


def main() -> None:
    ap = argparse.ArgumentParser(description="Raw clip -> finished vertical short.")
    ap.add_argument("input", help="path to the raw video")
    ap.add_argument("-o", "--output", default="short.mp4", help="output file name")
    ap.add_argument("--music", default="", help="music file to lay under the voice (ducked)")
    ap.add_argument("--grade", default="", help="color preset: warm|cool|cinematic|vivid|bw|vintage")
    ap.add_argument("--threshold-db", type=float, default=-30.0,
                    help="silence cutoff for jump-cuts (lower = cut more)")
    ap.add_argument("--max-words", type=int, default=5, help="caption words per line")
    ap.add_argument("--font-size", type=int, default=64, help="caption font size")
    a = ap.parse_args()
    print(T.make_short(a.input, a.output, a.music, a.grade,
                       a.threshold_db, a.max_words, a.font_size))


if __name__ == "__main__":
    main()
