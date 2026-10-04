"""Tools exposed to the agent. Each returns a JSON string."""
from __future__ import annotations

import csv
import json
from datetime import date, timedelta

from anthropic import beta_tool

from . import simulator, weather
from .db import connect


def _j(obj) -> str:
    return json.dumps(obj, default=str)


@beta_tool
def get_weather(latitude: float, longitude: float, start_date: str, end_date: str) -> str:
    """Get real hourly outdoor weather (Open-Meteo) summarised per day.

    Args:
        latitude: Latitude in degrees.
        longitude: Longitude in degrees.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day, YYYY-MM-DD (forecasts reach ~16 days ahead).
    """
    rows = weather.fetch_hourly(latitude, longitude, date.fromisoformat(start_date),
                                date.fromisoformat(end_date))
    days: dict[str, list[dict]] = {}
    for r in rows:
        days.setdefault(r["time"][:10], []).append(r)
    summary = [{"date": d,
                "temp_min": min(r["temp_c"] for r in v), "temp_max": max(r["temp_c"] for r in v),
                "rh_mean": round(sum(r["rh_pct"] for r in v) / len(v), 1),
                "radiation_mean_wm2": round(sum(r["radiation_wm2"] for r in v) / len(v), 1),
                "precip_mm": round(sum(r["precip_mm"] for r in v), 1)}
               for d, v in days.items()]
    return _j({"source": sorted({r["source"] for r in rows}), "days": summary})


@beta_tool
def build_greenhouse(name: str, crop_type: str, latitude: float, longitude: float,
                     area_sqm: float, temp_min: float = 18.0, temp_max: float = 26.0,
                     soil_min: float = 35.0, rh_max: float = 85.0) -> str:
    """Create a smart greenhouse with a standard sensor suite and actuators.

    Creates temperature, humidity, soil moisture, CO2 and light sensors plus a fan,
    heater, irrigation pump, grow light, shade screen and CO2 injector in auto mode.

    Args:
        name: Greenhouse name.
        crop_type: Crop grown, e.g. Tomatoes, Lettuce.
        latitude: Site latitude (used to fetch real weather).
        longitude: Site longitude.
        area_sqm: Floor area in square metres.
        temp_min: Heating setpoint in °C; heater runs below this.
        temp_max: Cooling setpoint in °C; fan runs above this.
        soil_min: Irrigation starts below this soil moisture %.
        rh_max: Fan runs above this relative humidity %.
    """
    gid = simulator.create_greenhouse(name, crop_type, latitude, longitude, area_sqm,
                                      {"temp_min": temp_min, "temp_max": temp_max,
                                       "soil_min": soil_min, "rh_max": rh_max})
    return _j({"greenhouse_id": gid, "sensors": [s for s, _ in simulator.SENSORS],
               "actuators": simulator.ACTUATORS})


@beta_tool
def list_greenhouses() -> str:
    """List all greenhouses with setpoints, actuator states and reading counts."""
    with connect() as c:
        out = []
        for g in c.execute("SELECT * FROM greenhouses"):
            acts = {a["type"]: a["current_state"] for a in c.execute(
                "SELECT type,current_state FROM actuators WHERE greenhouse_id=?", (g["id"],))}
            n = c.execute("SELECT COUNT(*) FROM sensor_readings r JOIN sensors s ON s.id="
                          "r.sensor_id WHERE s.greenhouse_id=?", (g["id"],)).fetchone()[0]
            out.append({**dict(g), "setpoints": json.loads(g["setpoints"]),
                        "actuators": acts, "readings": n})
    return _j(out)


@beta_tool
def get_status(greenhouse_id: int, hours: int = 24) -> str:
    """Summarise a greenhouse's sensor readings (min/mean/max/latest) over its last N hours.

    Args:
        greenhouse_id: Greenhouse id.
        hours: Window in hours ending at the latest reading.
    """
    with connect() as c:
        end = c.execute("SELECT MAX(recorded_at) FROM sensor_readings r JOIN sensors s ON s.id="
                        "r.sensor_id WHERE s.greenhouse_id=?", (greenhouse_id,)).fetchone()[0]
        if end is None:
            return _j({"error": "no readings yet; run simulate first"})
        rows = c.execute(
            "SELECT s.type, MIN(r.value) mn, AVG(r.value) av, MAX(r.value) mx FROM "
            "sensor_readings r JOIN sensors s ON s.id=r.sensor_id WHERE s.greenhouse_id=? AND "
            "r.recorded_at > datetime(?, ?) GROUP BY s.type",
            (greenhouse_id, end, f"-{int(hours)} hours")).fetchall()
        return _j({"as_of": end, "window_hours": hours,
                   "sensors": {r["type"]: {"min": round(r["mn"], 2), "mean": round(r["av"], 2),
                                           "max": round(r["mx"], 2)} for r in rows}})


@beta_tool
def set_setpoints(greenhouse_id: int, temp_min: float = -1, temp_max: float = -1,
                  soil_min: float = -1, rh_max: float = -1, co2_target: float = -1) -> str:
    """Change automation setpoints (pass -1 to leave a value unchanged). Affects future simulation.

    Args:
        greenhouse_id: Greenhouse id.
        temp_min: Heating setpoint °C.
        temp_max: Cooling setpoint °C.
        soil_min: Irrigation threshold, soil moisture %.
        rh_max: Humidity ceiling %.
        co2_target: CO2 target in ppm.
    """
    new = {k: v for k, v in dict(temp_min=temp_min, temp_max=temp_max, soil_min=soil_min,
                                  rh_max=rh_max, co2_target=co2_target).items() if v != -1}
    with connect() as c:
        row = c.execute("SELECT setpoints FROM greenhouses WHERE id=?", (greenhouse_id,)).fetchone()
        if row is None:
            return _j({"error": "greenhouse not found"})
        sp = {**json.loads(row[0]), **new}
        if sp["temp_min"] >= sp["temp_max"]:
            return _j({"error": "temp_min must be below temp_max"})
        c.execute("UPDATE greenhouses SET setpoints=? WHERE id=?", (json.dumps(sp), greenhouse_id))
    return _j({"setpoints": sp})


@beta_tool
def set_actuator(greenhouse_id: int, actuator_type: str, state: str) -> str:
    """Manually command an actuator; this takes it out of auto mode until set back to 'auto'.

    Args:
        greenhouse_id: Greenhouse id.
        actuator_type: One of ventilation_fan, heater, irrigation_pump, grow_light, shade_screen, co2_injector.
        state: 'on', 'off' or 'auto' (hand control back to the automation rules).
    """
    if state not in ("on", "off", "auto"):
        return _j({"error": "state must be on, off or auto"})
    with connect() as c:
        a = c.execute("SELECT id FROM actuators WHERE greenhouse_id=? AND type=?",
                      (greenhouse_id, actuator_type)).fetchone()
        if a is None:
            return _j({"error": "actuator not found"})
        if state == "auto":
            c.execute("UPDATE actuators SET is_auto=1 WHERE id=?", (a["id"],))
        else:
            c.execute("UPDATE actuators SET is_auto=0, current_state=? WHERE id=?", (state, a["id"]))
            c.execute("INSERT INTO actuator_log(actuator_id,action,trigger_source,note,commanded_at)"
                      " VALUES(?,?,?,?,datetime('now'))", (a["id"], state, "api", "agent command"))
    return _j({"ok": True, "actuator": actuator_type, "state": state})


@beta_tool
def simulate(greenhouse_id: int, start_date: str, end_date: str) -> str:
    """Simulate the greenhouse hour by hour under REAL weather for a date range.

    Stores sensor readings, weather and actuator events. Continues from the previous
    state, so run date ranges in chronological order.

    Args:
        greenhouse_id: Greenhouse id.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day, YYYY-MM-DD (max 120 days per call).
    """
    s, e = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if e < s or (e - s) > timedelta(days=120):
        return _j({"error": "invalid range (end before start, or longer than 120 days)"})
    try:
        return _j(simulator.simulate(greenhouse_id, s, e))
    except (ValueError, RuntimeError) as exc:
        return _j({"error": str(exc)})


@beta_tool
def export_dataset(greenhouse_id: int, path: str) -> str:
    """Export a greenhouse's hourly dataset (indoor sensors + outdoor weather) to CSV.

    Args:
        greenhouse_id: Greenhouse id.
        path: Output CSV path, e.g. datasets/tomatoes.csv.
    """
    with connect() as c:
        rows = c.execute(
            "SELECT r.recorded_at ts, s.type, r.value FROM sensor_readings r JOIN sensors s ON "
            "s.id=r.sensor_id WHERE s.greenhouse_id=? ORDER BY r.recorded_at", (greenhouse_id,)
        ).fetchall()
        if not rows:
            return _j({"error": "no readings; run simulate first"})
        wx = {r["time"]: r for r in c.execute(
            "SELECT * FROM weather_observations WHERE greenhouse_id=?", (greenhouse_id,))}
        acts = {}
        for r in c.execute(
                "SELECT l.commanded_at ts, a.type, l.action FROM actuator_log l JOIN actuators a "
                "ON a.id=l.actuator_id WHERE a.greenhouse_id=? ORDER BY l.id", (greenhouse_id,)):
            acts.setdefault(r["type"], []).append((r["ts"], r["action"]))
    table: dict[str, dict] = {}
    for r in rows:
        table.setdefault(r["ts"], {})[r["type"]] = r["value"]
    sensors = [s for s, _ in simulator.SENSORS]
    cols = ["timestamp", *[f"indoor_{s}" for s in sensors], "outdoor_temp_c", "outdoor_rh_pct",
            "outdoor_radiation_wm2", "outdoor_wind_ms", "outdoor_precip_mm", "weather_source",
            *[f"{a}_on" for a in simulator.ACTUATORS]]
    idx = {a: 0 for a in simulator.ACTUATORS}
    state = {a: 0 for a in simulator.ACTUATORS}
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for ts in sorted(table):
            for a in simulator.ACTUATORS:
                ev = acts.get(a, [])
                while idx[a] < len(ev) and ev[idx[a]][0] <= ts:
                    state[a] = 1 if ev[idx[a]][1] == "on" else 0
                    idx[a] += 1
            o = wx.get(ts)
            w.writerow([ts, *[table[ts].get(s) for s in sensors],
                        *([o["temp_c"], o["rh_pct"], o["radiation_wm2"], o["wind_ms"],
                           o["precip_mm"], o["source"]] if o else [None] * 6),
                        *[state[a] for a in simulator.ACTUATORS]])
    return _j({"path": path, "rows": len(table), "columns": cols})


ALL_TOOLS = [get_weather, build_greenhouse, list_greenhouses, get_status, set_setpoints,
             set_actuator, simulate, export_dataset]
