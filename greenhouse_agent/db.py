"""SQLite store. Table/column names follow ../greenhouse_schema.sql (MySQL),
trimmed to what the agents need, plus a `weather_observations` table."""
from __future__ import annotations

import os
import sqlite3

DB_PATH = os.environ.get("GREENHOUSE_DB", "greenhouse.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS greenhouses (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, crop_type TEXT,
  latitude REAL, longitude REAL, area_sqm REAL,
  setpoints TEXT NOT NULL DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sensors (
  id INTEGER PRIMARY KEY AUTOINCREMENT, greenhouse_id INTEGER NOT NULL REFERENCES greenhouses(id),
  name TEXT, type TEXT NOT NULL, unit TEXT NOT NULL, mqtt_topic TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS actuators (
  id INTEGER PRIMARY KEY AUTOINCREMENT, greenhouse_id INTEGER NOT NULL REFERENCES greenhouses(id),
  name TEXT, type TEXT NOT NULL, mqtt_command_topic TEXT UNIQUE,
  current_state TEXT NOT NULL DEFAULT 'off', is_auto INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sensor_readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sensor_id INTEGER NOT NULL REFERENCES sensors(id),
  value REAL NOT NULL, quality INTEGER NOT NULL DEFAULT 100, recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_readings ON sensor_readings(sensor_id, recorded_at);
CREATE TABLE IF NOT EXISTS actuator_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, actuator_id INTEGER NOT NULL REFERENCES actuators(id),
  action TEXT NOT NULL, trigger_source TEXT NOT NULL, note TEXT, commanded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS weather_observations (
  greenhouse_id INTEGER NOT NULL REFERENCES greenhouses(id), time TEXT NOT NULL,
  temp_c REAL, rh_pct REAL, radiation_wm2 REAL, wind_ms REAL, precip_mm REAL, source TEXT,
  PRIMARY KEY (greenhouse_id, time));
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
