import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Trend Viewer")

# ---------------------
# Upload CSV files
# ---------------------
uploaded_files = st.file_uploader(
    "Upload multiple CSV files (_DDMMYYYY_HHMMSS.csv)",
    accept_multiple_files=True,
    type=["csv"]
)

if not uploaded_files:
    st.info("👆 Upload one or more CSV files to begin")
    st.stop()

def get_time_from_filename(name):
    """Extract timestamp from filename format _DDMMYYYY_HHMMSS.csv"""
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m: return None
    day, month, year, h, mi, s = m.groups()
    return f"{day}-{month}-{year} {h}:{mi}:{s}"

data = []
for uploaded in uploaded_files:
    try:
        df = pd.read_csv(uploaded)
        df["timestamp"] = get_time_from_filename(uploaded.name)
        data.append(df)
    except Exception as e:
        st.warning(f"Could not read {uploaded.name}: {e}")

if not data:
    st.error("No valid CSVs found.")
    st.stop()

# Combine and clean
df = pd.concat(data)
df.dropna(subset=["timestamp"], inplace=True)

# ---------------------
# Sidebar filters
# ---------------------
with st.sidebar:
    st.header("⚙️ Controls")
    strike = st.selectbox("Select Strike Price", sorted(df["CE_strikePrice"].unique()))
    option_type = st.radio("Option Type", ["CE", "PE", "Both"])
    chart_type = st.radio("Chart Type", ["Line", "Bar"])
    plot_btn = st.button("Plot Charts")

# ---------------------
# Plot Function
# ---------------------
def plot_metric(metric, label):
    metric_map = {
        "lastPrice": "Price",
        "totalTradedVolume": "Volume",
        "changeinOpenInterest": "Open Interest Change"
    }
    metric_name = metric_map.get(metric, metric)
    st.subheader(f"{metric_name}")

    prefixes = []
    if option_type in ["CE", "Both"]: prefixes.append("CE_")
    if option_type in ["PE", "Both"]: prefixes.append("PE_")

    for prefix in prefixes:
        subset = df[df[f"{prefix}strikePrice"] == strike].copy()
        subset["time"] = pd.to_datetime(subset["timestamp"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
        subset = subset.sort_values("time")

        y_col = f"{prefix}{metric}"
        label_side = prefix.replace("_", "")

        if chart_type == "Line":
            fig = px.line(subset, x="time", y=y_col, title=f"{label_side} {metric_name}", markers=True)
        else:
            fig = px.bar(subset, x="time", y=y_col, title=f"{label_side} {metric_name}")

        fig.update_layout(autosize=True, height=500, xaxis_title="Time", yaxis_title=metric_name)
        st.plotly_chart(fig, use_container_width=True)

# ---------------------
# Plot charts
# ---------------------
if plot_btn:
    st.success(f"Showing charts for strike {strike}")
    for metric in ["lastPrice", "totalTradedVolume", "changeinOpenInterest"]:
        plot_metric(metric, metric)
