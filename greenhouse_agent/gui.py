"""Streamlit GUI: chat with the greenhouse agent, view dashboards, download datasets.

    streamlit run greenhouse_agent/gui.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from greenhouse_agent.agent import run  # noqa: E402
from greenhouse_agent.db import connect  # noqa: E402
from greenhouse_agent.tools import export_dataset  # noqa: E402

st.set_page_config(page_title="Smart Greenhouse Agent", page_icon="🌱", layout="wide")


def greenhouses() -> pd.DataFrame:
    with connect() as c:
        return pd.read_sql_query("SELECT id, name, crop_type, latitude, longitude, area_sqm,"
                                 " setpoints FROM greenhouses ORDER BY id", c)


def readings(gid: int) -> pd.DataFrame:
    with connect() as c:
        df = pd.read_sql_query(
            "SELECT r.recorded_at ts, s.type, r.value FROM sensor_readings r JOIN sensors s"
            " ON s.id=r.sensor_id WHERE s.greenhouse_id=? ORDER BY r.recorded_at", c, params=(gid,))
        wx = pd.read_sql_query("SELECT * FROM weather_observations WHERE greenhouse_id=?"
                               " ORDER BY time", c, params=(gid,))
        acts = pd.read_sql_query(
            "SELECT type, current_state, is_auto FROM actuators WHERE greenhouse_id=?", c,
            params=(gid,))
    return df, wx, acts


# ---------- sidebar ----------
with st.sidebar:
    st.title("🌱 Greenhouse Agent")
    key = os.environ.get("ANTHROPIC_API_KEY") or st.text_input(
        "Anthropic API key", type="password", help="Kept in memory only, never saved.")
    ghs = greenhouses()
    st.subheader("Greenhouses")
    if ghs.empty:
        st.caption("None yet. Ask the agent to build one in the Chat tab.")
        gid = None
    else:
        labels = {int(r.id): f"#{r.id} {r['name']} ({r.crop_type})" for _, r in ghs.iterrows()}
        gid = st.selectbox("Selected", list(labels), format_func=labels.get,
                           index=len(labels) - 1)
    if st.button("Clear chat"):
        st.session_state.pop("messages", None)
        st.session_state.pop("shown", None)
        st.rerun()

st.session_state.setdefault("messages", [])  # API conversation
st.session_state.setdefault("shown", [])     # (role, text) for display

chat_tab, dash_tab, data_tab = st.tabs(["💬 Chat", "📈 Dashboard", "📦 Dataset"])

# ---------- chat ----------
with chat_tab:
    st.caption("Try: *Build a tomato greenhouse in Nairobi, simulate 1–30 Sept 2026, "
               "then tell me how it did.*")
    for role, text in st.session_state["shown"]:
        with st.chat_message(role):
            st.markdown(text)
    prompt = st.chat_input("Tell the agent what to build, change or simulate…")
    if prompt:
        if not key:
            st.error("Enter your Anthropic API key in the sidebar first.")
        else:
            st.session_state["shown"].append(("user", prompt))
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"), st.spinner("Agent working (may take a minute)…"):
                try:
                    reply = run(anthropic.Anthropic(api_key=key), st.session_state["messages"])
                except anthropic.APIError as exc:
                    reply = f"⚠️ API error: {exc}"
            st.session_state["shown"].append(("assistant", reply or "(no reply)"))
            st.rerun()

# ---------- dashboard ----------
with dash_tab:
    if gid is None:
        st.info("No greenhouse yet.")
    else:
        df, wx, acts = readings(gid)
        g = ghs[ghs.id == gid].iloc[0]
        sp = json.loads(g.setpoints)
        c1, c2, c3 = st.columns(3)
        c1.metric("Crop", g.crop_type or "-")
        c2.metric("Location", f"{g.latitude:.2f}, {g.longitude:.2f}")
        c3.metric("Setpoints", f"{sp['temp_min']:.0f}–{sp['temp_max']:.0f} °C")
        if df.empty:
            st.info("No readings yet. Ask the agent to simulate a date range.")
        else:
            if "synthetic-fallback" in set(wx["source"]):
                st.warning("Some weather is SYNTHETIC (Open-Meteo unreachable) - not real weather.")
            else:
                st.success("Weather source: " + ", ".join(sorted(set(wx["source"]))))
            wide = df.pivot(index="ts", columns="type", values="value")
            wide.index = pd.to_datetime(wide.index)
            wxi = wx.set_index(pd.to_datetime(wx["time"]))
            st.subheader("Temperature: indoor vs outdoor")
            st.line_chart(pd.DataFrame({"indoor": wide["temperature"],
                                        "outdoor": wxi["temp_c"]}))
            a, b = st.columns(2)
            a.subheader("Humidity (%)")
            a.line_chart(wide["humidity"])
            b.subheader("Soil moisture (%)")
            b.line_chart(wide["soil_moisture"])
            a.subheader("CO₂ (ppm)")
            a.line_chart(wide["co2"])
            b.subheader("Light (W/m²)")
            b.line_chart(wide["light"])
            st.subheader("Actuators")
            acts["mode"] = acts["is_auto"].map({1: "auto", 0: "manual"})
            st.dataframe(acts[["type", "current_state", "mode"]], hide_index=True)

# ---------- dataset ----------
with data_tab:
    if gid is None:
        st.info("No greenhouse yet.")
    else:
        path = os.path.join(tempfile.gettempdir(), f"greenhouse_{gid}.csv")
        res = json.loads(export_dataset.call({"greenhouse_id": gid, "path": path}))
        if "error" in res:
            st.info(res["error"])
        else:
            data = pd.read_csv(path)
            st.write(f"{res['rows']} hourly rows, {len(res['columns'])} columns")
            st.dataframe(data.head(200))
            st.download_button("⬇️ Download CSV", data.to_csv(index=False),
                               file_name=f"greenhouse_{gid}.csv", mime="text/csv")
