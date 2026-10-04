"""Lightweight hourly greenhouse physics driven by real outdoor weather.

Not a CFD model: first-order heat/moisture/CO2 balances that react sensibly to
weather and actuators, good enough to generate realistic-looking labelled data.
"""
from __future__ import annotations

import json
import random
from datetime import datetime

from . import weather
from .db import connect

DEFAULT_SETPOINTS = {"temp_min": 18.0, "temp_max": 26.0, "rh_max": 85.0,
                     "soil_min": 35.0, "co2_target": 800.0, "light_min_wm2": 150.0}
SENSORS = [("temperature", "°C"), ("humidity", "%"), ("soil_moisture", "%"),
           ("co2", "ppm"), ("light", "W/m2")]
ACTUATORS = ["ventilation_fan", "heater", "irrigation_pump", "grow_light",
             "shade_screen", "co2_injector"]


def create_greenhouse(name, crop_type, lat, lon, area_sqm, setpoints=None) -> int:
    sp = {**DEFAULT_SETPOINTS, **(setpoints or {})}
    with connect() as c:
        gid = c.execute(
            "INSERT INTO greenhouses(name,crop_type,latitude,longitude,area_sqm,setpoints)"
            " VALUES(?,?,?,?,?,?)", (name, crop_type, lat, lon, area_sqm, json.dumps(sp))
        ).lastrowid
        for typ, unit in SENSORS:
            c.execute("INSERT INTO sensors(greenhouse_id,name,type,unit,mqtt_topic)"
                      " VALUES(?,?,?,?,?)",
                      (gid, f"{name} {typ}", typ, unit, f"greenhouse/{gid}/sensor/{typ}"))
        for typ in ACTUATORS:
            c.execute("INSERT INTO actuators(greenhouse_id,name,type,mqtt_command_topic)"
                      " VALUES(?,?,?,?)",
                      (gid, f"{name} {typ}", typ, f"greenhouse/{gid}/actuator/{typ}"))
    return gid


def _decide(state, sp, w):
    """Rule-based controller for actuators in auto mode."""
    return {
        "heater": state["temp"] < sp["temp_min"],
        "ventilation_fan": state["temp"] > sp["temp_max"] or state["rh"] > sp["rh_max"],
        "shade_screen": w["radiation_wm2"] > 700 and state["temp"] > sp["temp_max"] - 1,
        "irrigation_pump": state["soil"] < sp["soil_min"],
        "grow_light": 6 <= datetime.fromisoformat(w["time"]).hour <= 20
                      and w["radiation_wm2"] < sp["light_min_wm2"],
        "co2_injector": state["co2"] < sp["co2_target"] and w["radiation_wm2"] > 100
                        and not state["fan"],
    }


def simulate(gid: int, start, end) -> dict:
    """Run hourly steps over [start, end] using real weather; persist everything."""
    with connect() as c:
        g = c.execute("SELECT * FROM greenhouses WHERE id=?", (gid,)).fetchone()
        if g is None:
            raise ValueError(f"greenhouse {gid} not found")
        sp = json.loads(g["setpoints"])
        sensors = {r["type"]: r["id"] for r in
                   c.execute("SELECT id,type FROM sensors WHERE greenhouse_id=?", (gid,))}
        acts = {r["type"]: dict(r) for r in
                c.execute("SELECT * FROM actuators WHERE greenhouse_id=?", (gid,))}
        wx = weather.fetch_hourly(g["latitude"], g["longitude"], start, end)
        if not wx:
            raise RuntimeError("no weather data returned")
        last = c.execute(
            "SELECT s.type, r.value FROM sensor_readings r JOIN sensors s ON s.id=r.sensor_id"
            " WHERE s.greenhouse_id=? AND r.recorded_at=(SELECT MAX(recorded_at) FROM"
            " sensor_readings r2 JOIN sensors s2 ON s2.id=r2.sensor_id WHERE s2.greenhouse_id=?)",
            (gid, gid)).fetchall()
        prev = {r["type"]: r["value"] for r in last}
        state = {"temp": prev.get("temperature", wx[0]["temp_c"] + 2),
                 "rh": prev.get("humidity", 70.0), "soil": prev.get("soil_moisture", 50.0),
                 "co2": prev.get("co2", 450.0), "fan": False}
        rng = random.Random(gid * 1000 + start.toordinal())
        on = {t: a["current_state"] == "on" for t, a in acts.items()}
        alerts = 0
        for w in wx:
            ts = w["time"].replace("T", " ") + ":00"
            c.execute("INSERT OR REPLACE INTO weather_observations VALUES(?,?,?,?,?,?,?,?)",
                      (gid, ts, w["temp_c"], w["rh_pct"], w["radiation_wm2"],
                       w["wind_ms"], w["precip_mm"], w["source"]))
            want = _decide(state, sp, w)
            for typ, a in acts.items():
                if a["is_auto"] and want[typ] != on[typ]:
                    on[typ] = want[typ]
                    c.execute("INSERT INTO actuator_log(actuator_id,action,trigger_source,note,"
                              "commanded_at) VALUES(?,?,?,?,?)",
                              (a["id"], "on" if on[typ] else "off", "automation", None, ts))
            state["fan"] = on["ventilation_fan"]
            shade = 0.5 if on["shade_screen"] else 1.0
            sun = w["radiation_wm2"] * shade
            vent = (0.05 + 0.04 * w["wind_ms"]) + (0.45 if on["ventilation_fan"] else 0)
            state["temp"] += (vent * (w["temp_c"] - state["temp"])
                              + 0.012 * sun + (3.5 if on["heater"] else 0)
                              + (0.6 if on["grow_light"] else 0) - 0.15)
            state["rh"] += (vent * (w["rh_pct"] - state["rh"]) * 0.8
                            + (6 if on["irrigation_pump"] else 0)
                            - 0.004 * sun - 0.4 * (state["temp"] - 20) * 0.1)
            state["rh"] = min(100.0, max(20.0, state["rh"]))
            state["soil"] += ((12 if on["irrigation_pump"] else 0) + 0.4 * w["precip_mm"] * 0
                              - 0.35 - 0.0015 * sun - 0.03 * max(0, state["temp"] - 20))
            state["soil"] = min(100.0, max(5.0, state["soil"]))
            state["co2"] += (60 * (420 - state["co2"]) / 100 * (vent + 0.05)
                             + (150 if on["co2_injector"] else 0) - 0.02 * sun)
            state["co2"] = max(200.0, state["co2"])
            vals = {"temperature": state["temp"], "humidity": state["rh"],
                    "soil_moisture": state["soil"], "co2": state["co2"],
                    "light": sun + (80 if on["grow_light"] else 0)}
            noise = {"temperature": .15, "humidity": .8, "soil_moisture": .3,
                     "co2": 8, "light": 5}
            for typ, v in vals.items():
                c.execute("INSERT INTO sensor_readings(sensor_id,value,quality,recorded_at)"
                          " VALUES(?,?,?,?)",
                          (sensors[typ], round(max(0.0, v + rng.gauss(0, noise[typ])), 3),
                           rng.randint(92, 100), ts))
            if not sp["temp_min"] - 4 <= state["temp"] <= sp["temp_max"] + 6:
                alerts += 1
        for typ, a in acts.items():
            c.execute("UPDATE actuators SET current_state=? WHERE id=?",
                      ("on" if on[typ] else "off", a["id"]))
        sources = sorted({w["source"] for w in wx})
    return {"hours": len(wx), "weather_source": sources, "out_of_range_hours": alerts,
            "final_state": {k: round(v, 2) for k, v in state.items() if k != "fan"}}
