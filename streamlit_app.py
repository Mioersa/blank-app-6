import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Persistent Dual Panels)")

# --------------------
# Upload CSVs
# --------------------
files = st.file_uploader(
    "Upload multiple CSVs (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)
if not files:
    st.info("👆 Upload files to begin")
    st.stop()

# --------------------
# Extract timestamp from filename
# --------------------
def get_time_from_filename(name):
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None
    d, mo, y, h, mi, s = m.groups()
    return f"{d}-{mo}-{y} {h}:{mi}:{s}"

# --------------------
# Combine data
# --------------------
data = []
for f in files:
    try:
        df = pd.read_csv(f)
        df["timestamp"] = get_time_from_filename(f.name)
        data.append(df)
    except Exception as e:
        st.warning(f"{f.name}: {e}")
if not data:
    st.error("No valid CSVs found.")
    st.stop()

df = pd.concat(data)
df.dropna(subset=["timestamp"], inplace=True)
df = df.sort_values("timestamp").reset_index(drop=True)

# --------------------
# Δ calculations
# --------------------
for prefix in ["CE_", "PE_"]:
    if f"{prefix}totalTradedVolume" in df.columns:
        df[f"{prefix}volChange"] = df[f"{prefix}totalTradedVolume"].diff().fillna(0)
    if f"{prefix}openInterest" in df.columns:
        df[f"{prefix}oiChange"] = df[f"{prefix}openInterest"].diff().fillna(0)

# --------------------
# Helper: plot a single metric
# --------------------
def plot_metric(metric, display, df, strike, opt_type, chart_type):
    prefixes = []
    if opt_type in ["CE", "Both"]: prefixes.append("CE_")
    if opt_type in ["PE", "Both"]: prefixes.append("PE_")

    for pre in prefixes:
        tmp = df[df[f"{pre}strikePrice"] == strike].copy()
        tmp["time"] = pd.to_datetime(tmp["timestamp"], format="%d-%m-%Y %H:%M:%S")
        tmp = tmp.sort_values("time")

        if metric not in tmp.columns:
            continue

        fig_func = px.line if chart_type == "Line" else px.bar
        fig = fig_func(
            tmp, x="time", y=metric, title=f"{pre}{display}", markers=True
        )
        fig.update_layout(
            autosize=True,
            height=450,
            xaxis=dict(
                tickmode="linear",
                tickvals=tmp["time"],
                tickfont=dict(size=9),
                tickangle=-45
            ),
            xaxis_title="Time",
            yaxis_title=display,
        )
        st.plotly_chart(fig, use_container_width=True)

# --------------------
# Panel function (persistent plots)
# --------------------
def panel(name):
    st.subheader(name)
    key_suffix = name.replace(" ", "_")

    # input widgets
    strike = st.selectbox(
        f"{name} Strike", sorted(df["CE_strikePrice"].unique()), key=f"{key_suffix}_strike"
    )
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key_suffix}_type")
    chart_type = st.radio("Chart Type", ["Line", "Bar"], key=f"{key_suffix}_chart")

    # persist when plot clicked
    if st.button("Plot", key=f"{key_suffix}_btn"):
        st.session_state[f"{key_suffix}_plot"] = {
            "strike": strike,
            "opt_type": opt_type,
            "chart_type": chart_type,
        }

    # if stored plot exists, display it
    saved = st.session_state.get(f"{key_suffix}_plot", None)
    if saved:
        st.success(f"Strike {saved['strike']} | {saved['opt_type']}")
        plot_metric("CE_lastPrice" if saved["opt_type"] != "PE" else "PE_lastPrice",
                    "Price", df, saved["strike"], saved["opt_type"], saved["chart_type"])
        plot_metric("CE_volChange" if saved["opt_type"] != "PE" else "PE_volChange",
                    "Volume Δ", df, saved["strike"], saved["opt_type"], saved["chart_type"])
        plot_metric("CE_openInterest" if saved["opt_type"] != "PE" else "PE_openInterest",
                    "Open Interest", df, saved["strike"], saved["opt_type"], saved["chart_type"])
        plot_metric("CE_oiChange" if saved["opt_type"] != "PE" else "PE_oiChange",
                    "Open Interest Δ", df, saved["strike"], saved["opt_type"], saved["chart_type"])

# --------------------
# Layout (B below A)
# --------------------
panel("Panel A")
st.markdown("---")
panel("Panel B")
