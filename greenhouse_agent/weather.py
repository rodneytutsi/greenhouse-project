"""Real weather via Open-Meteo (free, no API key).

Falls back to a clearly-labelled synthetic climate model only when the network
call fails, so offline tests still run. Every record carries its `source`.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = ("temperature_2m,relative_humidity_2m,shortwave_radiation,"
          "wind_speed_10m,precipitation")
TIMEOUT = 20


def _rows(payload: dict, source: str) -> list[dict]:
    h = payload["hourly"]
    return [
        {
            "time": t,
            "temp_c": h["temperature_2m"][i],
            "rh_pct": h["relative_humidity_2m"][i],
            "radiation_wm2": h["shortwave_radiation"][i],
            "wind_ms": h["wind_speed_10m"][i] / 3.6,  # km/h -> m/s
            "precip_mm": h["precipitation"][i],
            "source": source,
        }
        for i, t in enumerate(h["time"])
        if h["temperature_2m"][i] is not None
    ]


def fetch_hourly(lat: float, lon: float, start: date, end: date) -> list[dict]:
    """Hourly observed/forecast weather for [start, end] inclusive."""
    # Archive data lags ~5 days; recent days come from the forecast API.
    cutoff = date.today() - timedelta(days=5)
    rows: list[dict] = []
    try:
        if start <= cutoff:
            a_end = min(end, cutoff)
            r = requests.get(ARCHIVE_URL, timeout=TIMEOUT, params={
                "latitude": lat, "longitude": lon, "hourly": HOURLY,
                "start_date": start.isoformat(), "end_date": a_end.isoformat(),
                "timezone": "UTC"})
            r.raise_for_status()
            rows += _rows(r.json(), "open-meteo-archive")
        if end > cutoff:
            f_start = max(start, cutoff + timedelta(days=1))
            r = requests.get(FORECAST_URL, timeout=TIMEOUT, params={
                "latitude": lat, "longitude": lon, "hourly": HOURLY,
                "start_date": f_start.isoformat(), "end_date": end.isoformat(),
                "timezone": "UTC"})
            r.raise_for_status()
            rows += _rows(r.json(), "open-meteo-forecast")
        return rows
    except (requests.RequestException, KeyError, ValueError):
        return synthetic_hourly(lat, lon, start, end)


def synthetic_hourly(lat: float, lon: float, start: date, end: date) -> list[dict]:
    """OFFLINE FALLBACK ONLY - not real weather. Seasonal + diurnal sine model."""
    rng = random.Random(f"{lat:.2f},{lon:.2f}")
    out = []
    t = datetime.combine(start, datetime.min.time())
    stop = datetime.combine(end, datetime.min.time()) + timedelta(days=1)
    while t < stop:
        doy = t.timetuple().tm_yday
        season = math.cos(2 * math.pi * (doy - (200 if lat >= 0 else 17)) / 365)
        mean = 27 - 0.45 * abs(lat) + 10 * season
        local_hour = (t.hour + lon / 15) % 24
        diurnal = -math.cos(2 * math.pi * (local_hour - 3) / 24)
        temp = mean + 5 * diurnal + rng.gauss(0, 0.8)
        sun = max(0.0, math.sin(math.pi * (local_hour - 6) / 12))
        out.append({
            "time": t.strftime("%Y-%m-%dT%H:%M"),
            "temp_c": round(temp, 2),
            "rh_pct": round(min(100, max(15, 70 - 20 * diurnal + rng.gauss(0, 4))), 1),
            "radiation_wm2": round(sun * (600 + 250 * season) * rng.uniform(0.6, 1), 1),
            "wind_ms": round(abs(rng.gauss(3, 1.5)), 2),
            "precip_mm": round(max(0.0, rng.gauss(-0.3, 0.5)), 2),
            "source": "synthetic-fallback",
        })
        t += timedelta(hours=1)
    return out
