import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Δ per Strike + Colored Panel B)")

# --------------------
# Upload CSVs
# --------------------
files = st.file_uploader(
    "Upload multiple CSVs (_DDMMYYYY_HHMMSS.csv)",
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

# --------------------
# Combine data
# --------------------
data = []
for f in files:
    df = pd.read_csv(f)
    df["timestamp"] = get_time_from_filename(f.name)
    data.append(df)

df = pd.concat(data)
df.dropna(subset=["timestamp"], inplace=True)
df = df.sort_values("timestamp").reset_index(drop=True)

# --------------------
# Compute per‑strike Δvolume & ΔOI
# --------------------
for prefix in ["CE_", "PE_"]:
    vol_col = f"{prefix}totalTradedVolume"
    oi_col = f"{prefix}openInterest"
    if vol_col not in df.columns:
        continue

    def calc_delta(group):
        group = group.sort_values("timestamp")
        group[f"{prefix}volChange"] = group[vol_col].diff().fillna(0)
        if oi_col in group:
            group[f"{prefix}oiChange"] = group[oi_col].diff().fillna(0)
        return group

    df = df.groupby(f"{prefix}strikePrice", group_keys=False).apply(calc_delta)

# --------------------
# Helper: plot metric
# --------------------
def plot_metric(metric, display, df, strike, opt_type, chart_type, color=None):
    prefixes = []
    if opt_type in ["CE", "Both"]:
        prefixes.append("CE_")
    if opt_type in ["PE", "Both"]:
        prefixes.append("PE_")

    for pre in prefixes:
        tmp = df[df[f"{pre}strikePrice"] == strike].copy()
        tmp["time"] = pd.to_datetime(tmp["timestamp"], format="%d-%m-%Y %H:%M:%S")
        tmp = tmp.sort_values("time")
        if f"{pre}{metric}" not in tmp.columns:
            continue

        fig_func = px.line if chart_type == "Line" else px.bar
        fig = fig_func(
            tmp,
            x="time",
            y=f"{pre}{metric}",
            title=f"{pre}{display}",
            markers=True,
        )
        if color:
            # apply fixed color
            if chart_type == "Line":
                fig.update_traces(line_color=color, marker_color=color)
            else:
                fig.update_traces(marker_color=color)
        fig.update_layout(
            autosize=True,
            height=450,
            xaxis=dict(
                tickmode="linear",
                tickvals=tmp["time"],
                tickfont=dict(size=9),
                tickangle=-45,
            ),
            xaxis_title="Time",
            yaxis_title=display,
        )
        st.plotly_chart(fig, use_container_width=True)

# --------------------
# Panel function
# --------------------
def panel(name, color=None, show_table=False):
    st.subheader(name)
    key = name.replace(" ", "_")

    strike = st.selectbox(
        f"{name} Strike",
        sorted(df["CE_strikePrice"].unique()),
        key=f"{key}_strike",
    )
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key}_type")
    chart_type = st.radio("Chart Type", ["Line", "Bar"], key=f"{key}_chart")

    # plot button
    if st.button("Plot", key=f"{key}_btn"):
        st.session_state[f"{key}_plot"] = {
            "strike": strike,
            "opt_type": opt_type,
            "chart_type": chart_type,
        }

    saved = st.session_state.get(f"{key}_plot", None)
    if saved:
        st.success(f"Strike: {saved['strike']} | Type: {saved['opt_type']}")
        # charts
        plot_metric("lastPrice", "Price", df, saved["strike"], saved["opt_type"], saved["chart_type"], color)
        plot_metric("volChange", "Volume Δ", df, saved["strike"], saved["opt_type"], saved["chart_type"], color)
        plot_metric("openInterest", "Open Interest", df, saved["strike"], saved["opt_type"], saved["chart_type"], color)
        plot_metric("oiChange", "Open Interest Δ", df, saved["strike"], saved["opt_type"], saved["chart_type"], color)

        # show Δ table
        if show_table:
            st.markdown("#### 🔍 Volume Δ table")
            prefixes = ["CE_", "PE_"] if saved["opt_type"] == "Both" else [f"{saved['opt_type']}_"]
            for pre in prefixes:
                cols = [f"{pre}strikePrice", "timestamp", f"{pre}totalTradedVolume", f"{pre}volChange"]
                sub = df[df[f"{pre}strikePrice"] == saved["strike"]][cols].copy()
                sub.rename(columns={
                    f"{pre}strikePrice": "Strike",
                    f"{pre}totalTradedVolume": "Total Volume",
                    f"{pre}volChange": "Volume Δ"
                }, inplace=True)
                st.dataframe(sub.reset_index(drop=True), use_container_width=True)

# --------------------
# Layout: Panel A then B (green)
# --------------------
panel("Panel A", color=None, show_table=True)
st.markdown("---")
panel("Panel B", color="green", show_table=True)
