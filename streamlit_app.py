import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Enhanced)")

# ---------------------
# Upload files
# ---------------------
uploaded_files = st.file_uploader(
    "Upload multiple CSV files (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("👆 Upload option-chain CSVs to start.")
    st.stop()

def get_time_from_filename(name):
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m: return None
    d, mth, y, h, mi, s = m.groups()
    return f"{d}-{mth}-{y} {h}:{mi}:{s}"

data = []
for file in uploaded_files:
    try:
        df = pd.read_csv(file)
        df["timestamp"] = get_time_from_filename(file.name)
        data.append(df)
    except Exception as e:
        st.warning(f"{file.name}: {e}")

if not data:
    st.error("No valid CSV processed.")
    st.stop()

df = pd.concat(data)
df.dropna(subset=["timestamp"], inplace=True)

# ---------------------
# Compute Δ columns
# ---------------------
df = df.sort_values("timestamp").reset_index(drop=True)
for prefix in ["CE_", "PE_"]:
    if f"{prefix}totalTradedVolume" in df.columns:
        df[f"{prefix}volChange"] = df[f"{prefix}totalTradedVolume"].diff().fillna(0)
    if f"{prefix}openInterest" in df.columns:
        df[f"{prefix}oiChange"] = df[f"{prefix}openInterest"].diff().fillna(0)

# ---------------------
# Chart panel function
# ---------------------
def chart_panel(panel_title):
    st.subheader(panel_title)
    c = st.container()

    with c:
        strike = st.selectbox("Strike", sorted(df["CE_strikePrice"].unique()), key=panel_title+"_strike")
        opt_type = st.radio("Option Type", ["CE","PE","Both"], key=panel_title+"_opt")
        chart_type = st.radio("Chart Type", ["Line","Bar"], key=panel_title+"_chart")
        plot_btn = st.button("Plot", key=panel_title+"_btn")

        def plot_metric(metric_col, display_name):
            prefixes = []
            if opt_type in ["CE","Both"]: prefixes.append("CE_")
            if opt_type in ["PE","Both"]: prefixes.append("PE_")

            for pre in prefixes:
                tmp = df[df[f"{pre}strikePrice"] == strike].copy()
                tmp["time"] = pd.to_datetime(tmp["timestamp"], format="%d-%m-%Y %H:%M:%S")
                tmp = tmp.sort_values("time")

                if metric_col not in tmp.columns:
                    continue

                fig = (px.line if chart_type=="Line" else px.bar)(
                    tmp, x="time", y=f"{pre}{metric_col}",
                    markers=True, title=f"{pre}{display_name}"
                )
                fig.update_layout(
                    autosize=True,
                    height=500,
                    xaxis=dict(tickmode="linear", tickvals=tmp["time"], tickfont=dict(size=10), tickangle=-45),
                    xaxis_title="Time",
                    yaxis_title=display_name
                )
                st.plotly_chart(fig, use_container_width=True)
        
        if plot_btn:
            st.success(f"Strike: {strike} | Type: {opt_type}")
            plot_metric("lastPrice", "Price")
            plot_metric("volChange", "Volume Δ")
            plot_metric("openInterest", "Open Interest")
            plot_metric("oiChange", "Open Interest Δ")

# ---------------------
# Two independent panels
# ---------------------
col1, col2 = st.columns(2)
with col1:
    chart_panel("Panel A")

with col2:
    chart_panel("Panel B")
