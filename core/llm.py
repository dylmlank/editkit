"""OpenRouter chat loop shared by the standalone agent and the companion window.

The kits originally called the Anthropic Messages API directly. They now route
through OpenRouter's OpenAI-compatible endpoint, so ANY OpenRouter model — free
or paid — works by setting its slug in .env. Tools are still authored once in
core.tools (Anthropic-style `input_schema`); here we translate them to OpenAI's
function-tool shape and run the tool-use loop.
"""
from __future__ import annotations

import json
import os
from typing import Callable

from openai import OpenAI

from config import BASE_URL, MODEL


def make_client() -> OpenAI:
    """Build an OpenRouter client, or raise a clear error if unconfigured."""
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No OpenRouter API key — add OPENROUTER_API_KEY=sk-or-v1-... to .env.")
    if not MODEL:
        raise RuntimeError(
            "No model set — add an OpenRouter model slug to .env "
            "(e.g. openai/gpt-oss-120b:free). It must support tool calling.")
    return OpenAI(base_url=BASE_URL, api_key=key)


def _openai_tools(tools: list) -> list:
    """Anthropic {name, description, input_schema} -> OpenAI function tools."""
    return [{"type": "function",
             "function": {"name": t["name"],
                          "description": t.get("description", ""),
                          "parameters": t["input_schema"]}}
            for t in tools]


def run_loop(client: OpenAI, tools: list, dispatch_fn: Callable[[str, dict], str],
             system: str, messages: list, log: Callable[[str], None],
             max_tokens: int = 4096) -> None:
    """Drive the model until it stops calling tools. `messages` is mutated in
    place so multi-turn history carries across calls. `dispatch_fn(name, args)`
    runs a tool and returns its text result."""
    oai_tools = _openai_tools(tools)
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system})
    while True:
        resp = client.chat.completions.create(
            model=MODEL, max_tokens=max_tokens, tools=oai_tools,
            tool_choice="auto", messages=messages)
        msg = resp.choices[0].message
        entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name,
                              "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]
        messages.append(entry)
        if msg.content and msg.content.strip():
            log(msg.content.strip())
        if not msg.tool_calls:
            return
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            out = dispatch_fn(tc.function.name, args)
            log(f"  · {tc.function.name} -> {str(out)[:160]}")
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": str(out)})
