import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ---------------------------------------------------------------------
# APP SETTINGS
# ---------------------------------------------------------------------

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Auto Strike From First File · Dual Panels)")

# ---------------------------------------------------------------------
# FILE UPLOAD + CLEAR BUTTON
# ---------------------------------------------------------------------

if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = None

if st.button("🗑️ Clear uploaded files"):
    st.session_state.clear()
    st.experimental_rerun()

uploaded = st.file_uploader(
    "Upload multiple CSV files (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)
if uploaded:
    st.session_state["uploaded_files"] = uploaded

files = st.session_state.get("uploaded_files", [])
if not files:
    st.info("👆 Upload option‑chain CSVs to start")
    st.stop()

# ---------------------------------------------------------------------
# STRIKE COLUMN DETECTION - from first file only
# ---------------------------------------------------------------------

first_file = files[0]
try:
    temp_df = pd.read_csv(first_file)
    temp_df.columns = [c.strip().replace(" ", "_") for c in temp_df.columns]
    strike_cols = [c for c in temp_df.columns if re.search("strike", c, re.IGNORECASE)]
except Exception as e:
    st.error(f"⚠️ Error reading first file: {e}")
    st.stop()

if not strike_cols:
    st.error("❌ No column with 'strike' in name found in the first file.")
    st.write("Detected columns:", temp_df.columns.tolist())
    st.stop()

strike_col = strike_cols[0]
try:
    strike_values = sorted(pd.to_numeric(temp_df[strike_col], errors="coerce").dropna().unique())
except Exception:
    strike_values = sorted(temp_df[strike_col].dropna().unique())

if not len(strike_values):
    st.error(f"No valid values in `{strike_col}`.")
    st.stop()

selected_strike = st.selectbox(f"Select strike value from `{strike_col}` of first file", strike_values)
st.markdown("---")

# ---------------------------------------------------------------------
# HELPER: parse timestamp + HHMM label from filename
# ---------------------------------------------------------------------

def parse_filename(name):
    m = re.search(r"(\d{2})(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None, None
    d, mo, y, h, mi, s = m.groups()
    return f"{d}-{mo}-{y} {h}:{mi}:{s}", f"T{h}{mi}"  # prefix T ➜ label

# ---------------------------------------------------------------------
# READ + COMBINE FILES
# ---------------------------------------------------------------------

frames = []
for f in files:
    try:
        df = pd.read_csv(f)
        if df.empty:
            st.warning(f"⚠️ Skipped empty file: {f.name}")
            continue
    except Exception as e:
        st.warning(f"⚠️ Could not read {f.name}: {e}")
        continue

    ts, lbl = parse_filename(f.name)
    df["timestamp"] = ts
    df["time_label"] = lbl
    frames.append(df)

if not frames:
    st.error("❌ All uploaded files empty or invalid")
    st.stop()

df = pd.concat(frames)
df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
df.columns = [c.strip().replace(" ", "_") for c in df.columns]

# ---------------------------------------------------------------------
# COMPUTE ΔVOLUME AND ΔOI PER STRIKE
# ---------------------------------------------------------------------

for prefix in ["CE_", "PE_"]:
    vol, oi, strike = f"{prefix}totalTradedVolume", f"{prefix}openInterest", f"{prefix}strikePrice"
    if not all(c in df.columns for c in [vol, oi, strike]):
        continue

    def add_delta(g):
        g = g.sort_values("timestamp")
        g[f"{prefix}volChange"] = g[vol].diff().fillna(0)
        g[f"{prefix}oiChange"] = g[oi].diff().fillna(0)
        return g

    df = df.groupby(strike, group_keys=False).apply(add_delta)

# ---------------------------------------------------------------------
# PLOT HELPER
# ---------------------------------------------------------------------

def plot_metric(metric, label, df, strike, opt_type, chart_type, color=None):
    prefixes = ["CE_", "PE_"] if opt_type == "Both" else [f"{opt_type}_"]

    for pre in prefixes:
        col, s_col = f"{pre}{metric}", f"{pre}strikePrice"
        if col not in df.columns or s_col not in df.columns:
            continue

        tmp = df[df[s_col] == strike].copy().sort_values("timestamp")
        if tmp.empty:
            continue

        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0)
        tmp["time_label"] = tmp["time_label"].astype(str)

        fig = (
            px.line(tmp, x="time_label", y=col, title=f"{pre}{label}", markers=True)
            if chart_type == "Line"
            else px.bar(tmp, x="time_label", y=col, title=f"{pre}{label}")
        )

        if color:
            if chart_type == "Line":
                fig.update_traces(line_color=color, marker_color=color)
            else:
                fig.update_traces(marker_color=color)

        fig.update_layout(
            height=400,
            xaxis=dict(
                type="category",
                categoryorder="array",
                categoryarray=list(tmp["time_label"]),
                tickangle=-45,
                tickfont=dict(size=10),
            ),
            xaxis_title="Time (HHMM)",
            yaxis_title=label,
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------
# PANEL DEFINITION (uses selected_strike)
# ---------------------------------------------------------------------

def panel(name, color=None):
    st.subheader(name)
    key = name.replace(" ", "_")

    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key}_type", horizontal=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        price_chart = st.radio("Price", ["Line", "Bar"], key=f"{key}_p", horizontal=True)
    with c2:
        vol_chart = st.radio("ΔVolume", ["Line", "Bar"], key=f"{key}_v", horizontal=True)
    with c3:
        oi_chart = st.radio("ΔOI", ["Line", "Bar"], key=f"{key}_o", horizontal=True)

    if st.button("Plot", key=f"{key}_btn"):
        st.session_state[f"{key}_plot"] = {
            "strike": selected_strike,
            "opt_type": opt_type,
            "price_chart": price_chart,
            "vol_chart": vol_chart,
            "oi_chart": oi_chart,
        }

    s = st.session_state.get(f"{key}_plot")
    if s:
        st.success(f"{s['opt_type']} | Strike {s['strike']}")
        plot_metric("lastPrice", "Price", df, s["strike"], s["opt_type"], s["price_chart"], color)
        plot_metric("volChange", "ΔVolume", df, s["strike"], s["opt_type"], s["vol_chart"], color)
        plot_metric("oiChange", "ΔOI (per strike)", df, s["strike"], s["opt_type"], s["oi_chart"], color)

# ---------------------------------------------------------------------
# LAYOUT: PANEL A (default), PANEL B (green)
# ---------------------------------------------------------------------

panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")


