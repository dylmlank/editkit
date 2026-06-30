@echo off
title EditKit Companion
cd /d E:\editkit
"C:\Users\dylan\.local\bin\uv.exe" run --python 3.12 --with anthropic --with faster-whisper python companion.py
pause
