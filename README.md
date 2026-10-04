still in progress. Be patient!!

## Greenhouse agent

An AI agent (Claude API tool use) that builds smart greenhouses, manages their
automation, simulates them under real weather (Open-Meteo, no key needed) and
exports CSV datasets.

```bash
pip install -r greenhouse_agent/requirements.txt
export ANTHROPIC_API_KEY=...
python -m greenhouse_agent.agent "Build a tomato greenhouse in Nairobi, simulate Sept 2026, export a dataset"
python -m greenhouse_agent.agent        # interactive
```

Data goes to a SQLite file (`greenhouse.db`, override with `GREENHOUSE_DB`) using the table
names from `greenhouse_schema.sql`. If Open-Meteo is unreachable, rows are tagged
`weather_source=synthetic-fallback` (not real weather) and the agent tells you.
