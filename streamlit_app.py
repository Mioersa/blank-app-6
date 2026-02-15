import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (No Hour‑Grouping, HHMM Labels)")

# ---------------- upload ----------------
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = None
clear = st.button("🗑️ Clear uploaded files")
if clear:
    st.session_state.clear()
    st.experimental_rerun()

uploaded = st.file_uploader(
    "Upload multiple CSV files (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"], accept_multiple_files=True)
if uploaded:
    st.session_state["uploaded_files"] = uploaded

files = st.session_state.get("uploaded_files", [])
if not files:
    st.info("👆 Upload option‑chain CSVs to start")
    st.stop()

def parse_filename(name):
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None, None
    d, mo, y, h, mi, s = m.groups()
    return f"{d}-{mo}-{y} {h}:{mi}:{s}", f"T{h}{mi}"  # ---- prefix T makes label categorical text

frames = []
for f in files:
    df = pd.read_csv(f)
    ts, lbl = parse_filename(f.name)
    df["timestamp"] = ts
    df["time_label"] = lbl
    frames.append(df)

df = pd.concat(frames)
df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
df.columns = [c.strip().replace(" ", "_") for c in df.columns]

# ---------------- deltas ----------------
for pre in ["CE_", "PE_"]:
    vol, oi, strike = f"{pre}totalTradedVolume", f"{pre}openInterest", f"{pre}strikePrice"
    if not all(c in df.columns for c in [vol, oi, strike]): 
        continue
    def add_delta(g):
        g = g.sort_values("timestamp")
        g[f"{pre}volChange"] = g[vol].diff().fillna(0)
        g[f"{pre}oiChange"] = g[oi].diff().fillna(0)
        return g
    df = df.groupby(strike, group_keys=False).apply(add_delta)

# ---------------- plot helper ----------------
def plot_metric(metric, label, df, strike, opt_type, chart_type, color=None):
    prefixes = ["CE_", "PE_"] if opt_type == "Both" else [f"{opt_type}_"]
    for pre in prefixes:
        col, s_col = f"{pre}{metric}", f"{pre}strikePrice"
        if col not in df.columns or s_col not in df.columns: 
            continue
        tmp = df[df[s_col] == strike].copy().sort_values("timestamp")
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0)
        tmp["time_label"] = tmp["time_label"].astype(str)

        fig_func = px.line if chart_type == "Line" else px.bar
        args = dict(x="time_label", y=col, title=f"{pre}{label}")
        if chart_type == "Line": args["markers"] = True
        fig = fig_func(tmp, **args)
        if color:
            if chart_type == "Line": fig.update_traces(line_color=color, marker_color=color)
            else: fig.update_traces(marker_color=color)

        fig.update_layout(
            height=400,
            xaxis=dict(
                type="category",                # <--- treat x purely as category
                categoryorder="array",
                categoryarray=list(tmp["time_label"]),  # keep original order
                tickangle=-45,
                tickfont=dict(size=10)
            ),
            xaxis_title="Time (HHMM)",
            yaxis_title=label,
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------- panel ----------------
def panel(name, color=None):
    st.subheader(name)
    key = name.replace(" ", "_")
    if "CE_strikePrice" in df.columns:
        strikes = sorted(pd.to_numeric(df["CE_strikePrice"], errors="coerce").dropna().unique())
    elif "PE_strikePrice" in df.columns:
        strikes = sorted(pd.to_numeric(df["PE_strikePrice"], errors="coerce").dropna().unique())
    else:
        st.warning("No strike column found.")
        return

    strike = st.selectbox(f"{name} Strike", strikes, key=f"{key}_strike")
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key}_type", horizontal=True)

    c1, c2, c3 = st.columns(3)
    with c1: price_chart = st.radio("Price", ["Line", "Bar"], key=f"{key}_p", horizontal=True)
    with c2: vol_chart   = st.radio("ΔVolume", ["Line", "Bar"], key=f"{key}_v", horizontal=True)
    with c3: oi_chart    = st.radio("ΔOI", ["Line", "Bar"], key=f"{key}_o", horizontal=True)

    if st.button("Plot", key=f"{key}_btn"):
        st.session_state[f"{key}_plot"] = {
            "strike": strike, "opt_type": opt_type,
            "price_chart": price_chart, "vol_chart": vol_chart, "oi_chart": oi_chart
        }

    s = st.session_state.get(f"{key}_plot")
    if s:
        st.success(f"{s['opt_type']} | Strike {s['strike']}")
        plot_metric("lastPrice", "Price", df, s["strike"], s["opt_type"], s["price_chart"], color)
        plot_metric("volChange", "ΔVolume", df, s["strike"], s["opt_type"], s["vol_chart"], color)
        plot_metric("oiChange", "ΔOI (per strike)", df, s["strike"], s["opt_type"], s["oi_chart"], color)

# ---------------- layout ----------------
panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")


