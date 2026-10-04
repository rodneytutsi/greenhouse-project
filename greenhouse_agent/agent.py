"""Greenhouse agent: builds, manages and generates datasets for smart greenhouses.

    export ANTHROPIC_API_KEY=...
    python -m greenhouse_agent.agent "Build a tomato greenhouse in Nairobi and make a 30-day dataset"
    python -m greenhouse_agent.agent            # interactive chat
"""
from __future__ import annotations

import sys
from datetime import date

import anthropic

from .tools import ALL_TOOLS

MODEL = "claude-opus-5-5"

SYSTEM = f"""You are a greenhouse operations agent. Today is {date.today().isoformat()}.
You can build smart greenhouses (sensors + actuators), tune their automation setpoints,
simulate them hour by hour under REAL weather (Open-Meteo), inspect their status and export
CSV datasets.

Guidelines:
- Choose latitude/longitude for any place the user names, and sensible setpoints for the crop.
- Simulate in chronological order. Past dates use observed weather; dates up to ~16 days
  ahead use forecasts.
- Always check `weather_source` in tool results. If it contains 'synthetic-fallback', the
  weather API was unreachable: tell the user the data is NOT real weather.
- After simulating, call get_status and sanity-check results (temperatures, humidity, soil
  moisture) and adjust setpoints and re-simulate if the climate is out of range for the crop.
- Report what you built, key statistics and file paths briefly."""


def run(client: anthropic.Anthropic, messages: list[dict]) -> str:
    runner = client.beta.messages.tool_runner(
        model=MODEL, max_tokens=16000, system=SYSTEM, tools=ALL_TOOLS, messages=messages,
        thinking={"type": "adaptive"}, output_config={"effort": "medium"},
    )
    last = None
    for message in runner:
        last = message
        messages.append({"role": "assistant", "content": message.content})
        resp = runner.generate_tool_call_response()
        if resp is not None:
            messages.append(resp)
    return "".join(b.text for b in last.content if b.type == "text") if last else ""


def main() -> None:
    client = anthropic.Anthropic()
    messages: list[dict] = []
    if len(sys.argv) > 1:
        messages.append({"role": "user", "content": " ".join(sys.argv[1:])})
        print(run(client, messages))
        return
    while True:
        try:
            q = input("you> ").strip()
        except EOFError:
            break
        if q in ("", "exit", "quit"):
            break
        messages.append({"role": "user", "content": q})
        print(run(client, messages))


if __name__ == "__main__":
    main()
