import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (ΔVolume + ΔOI per Strike)")

# -----------------------------------------
# Upload CSVs
# -----------------------------------------
files = st.file_uploader(
    "Upload multiple CSV files (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)
if not files:
    st.info("👆 Upload option-chain CSVs to start")
    st.stop()

def get_time_from_filename(name):
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None
    d, mo, y, h, mi, s = m.groups()
    return f"{d}-{mo}-{y} {h}:{mi}:{s}"

# -----------------------------------------
# Combine all uploaded data
# -----------------------------------------
frames = []
for f in files:
    df = pd.read_csv(f)
    df["timestamp"] = get_time_from_filename(f.name)
    frames.append(df)

df = pd.concat(frames)
df.dropna(subset=["timestamp"], inplace=True)
df = df.sort_values("timestamp").reset_index(drop=True)

# -----------------------------------------
# Compute per‑strike ΔVolume and ΔOI
# -----------------------------------------
for prefix in ["CE_", "PE_"]:
    vol_col = f"{prefix}totalTradedVolume"
    oi_col = f"{prefix}openInterest"
    if vol_col not in df.columns or oi_col not in df.columns:
        continue

    def add_deltas(group):
        group = group.sort_values("timestamp")
        # Δ relative to previous timestamp of same strike
        group[f"{prefix}volChange"] = group[vol_col].diff().fillna(0)
        group[f"{prefix}oiChange"] = group[oi_col].diff().fillna(0)
        # Δ of Δ = change in ΔOI relative to prior file (same strike)
        group[f"{prefix}oiDeltaDelta"] = group[f"{prefix}oiChange"].diff().fillna(0)
        return group

    df = df.groupby(f"{prefix}strikePrice", group_keys=False).apply(add_deltas)

# -----------------------------------------
# Helper function for plotting
# -----------------------------------------
def plot_metric(metric, label, df, strike, opt_type, chart_type, color=None):
    prefixes = []
    if opt_type in ["CE", "Both"]:
        prefixes.append("CE_")
    if opt_type in ["PE", "Both"]:
        prefixes.append("PE_")

    for pre in prefixes:
        col = f"{pre}{metric}"
        if col not in df.columns:
            continue
        tmp = df[df[f"{pre}strikePrice"] == strike].copy()
        tmp["time"] = pd.to_datetime(tmp["timestamp"], format="%d-%m-%Y %H:%M:%S")
        tmp = tmp.sort_values("time")

        fig_func = px.line if chart_type == "Line" else px.bar
        fig = fig_func(tmp, x="time", y=col, title=f"{pre}{label}", markers=True)
        if color:
            if chart_type == "Line":
                fig.update_traces(line_color=color, marker_color=color)
            else:
                fig.update_traces(marker_color=color)
        fig.update_layout(
            autosize=True,
            height=400,
            xaxis=dict(
                tickmode="linear",
                tickvals=tmp["time"],
                tickangle=-45,
                tickfont=dict(size=9),
            ),
            xaxis_title="Time",
            yaxis_title=label,
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------
# Panel setup (persistent via session_state)
# -----------------------------------------
def panel(name, color=None):
    st.subheader(name)
    key = name.replace(" ", "_")

    strike = st.selectbox(
        f"{name} Strike",
        sorted(df["CE_strikePrice"].unique()),
        key=f"{key}_strike",
    )
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key}_type")
    chart_type = st.radio("Chart Type", ["Line", "Bar"], key=f"{key}_chart")

    if st.button("Plot", key=f"{key}_btn"):
        st.session_state[f"{key}_plot"] = {
            "strike": strike,
            "opt_type": opt_type,
            "chart_type": chart_type,
        }

    saved = st.session_state.get(f"{key}_plot", None)
    if saved:
        st.success(f"Strike {saved['strike']} | {saved['opt_type']}")
        plot_metric("lastPrice", "Price", df, saved["strike"], saved["opt_type"], saved["chart_type"], color)
        plot_metric("volChange", "ΔVolume", df, saved["strike"], saved["opt_type"], saved["chart_type"], color)
        plot_metric("oiDeltaDelta", "ΔOI (per strike)", df, saved["strike"], saved["opt_type"], saved["chart_type"], color)

# -----------------------------------------
# Layout: Panel A followed by Panel B (green)
# -----------------------------------------
panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")
