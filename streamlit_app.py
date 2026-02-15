import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (ΔVolume + ΔOI per Strike | Filename Time Labels)")

# -----------------------------------------
# Upload CSVs
# -----------------------------------------
files = st.file_uploader(
    "Upload multiple CSV files (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)
if not files:
    st.info("👆 Upload option‑chain CSVs to start")
    st.stop()

def get_time_from_filename(name):
    """Extract readable timestamp and HHMM label from filename"""
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None, None
    d, mo, y, h, mi, s = m.groups()
    ts = f"{d}-{mo}-{y} {h}:{mi}:{s}"
    short = f"{h}{mi}"  # HHMM label to show on x-axis
    return ts, short

# -----------------------------------------
# Combine uploaded CSVs
# -----------------------------------------
frames = []
for f in files:
    df = pd.read_csv(f)
    full_ts, short_label = get_time_from_filename(f.name)
    df["timestamp"] = full_ts
    df["time_label"] = short_label  # new column for concise x-axis
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
    strike_col = f"{prefix}strikePrice"
    if vol_col not in df.columns or oi_col not in df.columns or strike_col not in df.columns:
        continue

    def add_deltas(group):
        group = group.sort_values("timestamp")
        group[f"{prefix}volChange"] = group[vol_col].diff().fillna(0)
        group[f"{prefix}oiChange"] = group[oi_col].diff().fillna(0)
        return group

    df = df.groupby(strike_col, group_keys=False).apply(add_deltas)

# -----------------------------------------
# Plot helper (x‑labels from filename)
# -----------------------------------------
def plot_metric(metric, label, df, strike, opt_type, chart_type, color=None):
    prefixes = []
    if opt_type in ["CE", "Both"]:
        prefixes.append("CE_")
    if opt_type in ["PE", "Both"]:
        prefixes.append("PE_")

    for pre in prefixes:
        col = f"{pre}{metric}"
        s_col = f"{pre}strikePrice"
        if col not in df.columns or s_col not in df.columns:
            continue

        tmp = df[df[s_col] == strike].copy()
        tmp = tmp.sort_values("timestamp")
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0)

        # Every timestamp gets its HHMM label
        x_labels = tmp["time_label"].tolist()

        fig_func = px.line if chart_type == "Line" else px.bar
        fig = fig_func(tmp, x="time_label", y=col, title=f"{pre}{label}", markers=True)

        if color:
            if chart_type == "Line":
                fig.update_traces(line_color=color, marker_color=color)
            else:
                fig.update_traces(marker_color=color)

        fig.update_layout(
            height=400,
            xaxis=dict(
                tickmode="array",
                tickvals=x_labels,
                ticktext=x_labels,
                ticks="outside",
                tickangle=-45,
                tickfont=dict(size=10),
            ),
            xaxis_title="Time (HHMM)",
            yaxis_title=label,
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------
# Panel definition
# -----------------------------------------
def panel(name, color=None):
    st.subheader(name)
    key = name.replace(" ", "_")

    # ensure numeric strike list
    if "CE_strikePrice" in df.columns:
        strike_list = sorted(pd.to_numeric(df["CE_strikePrice"], errors="coerce").dropna().unique())
    else:
        strike_list = []

    if not strike_list:
        st.warning("No valid strike prices found.")
        return

    strike = st.selectbox(f"{name} Strike", strike_list, key=f"{key}_strike")
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key}_type", horizontal=True)

    st.markdown("**Chart Types** (choose per metric):")
    c1, c2, c3 = st.columns(3)
    with c1:
        price_chart = st.radio("Price", ["Line", "Bar"], key=f"{key}_price", horizontal=True)
    with c2:
        vol_chart = st.radio("ΔVolume", ["Line", "Bar"], key=f"{key}_vol", horizontal=True)
    with c3:
        oi_chart = st.radio("ΔOI (per strike)", ["Line", "Bar"], key=f"{key}_oi", horizontal=True)

    if st.button("Plot", key=f"{key}_btn"):
        st.session_state[f"{key}_plot"] = {
            "strike": strike,
            "opt_type": opt_type,
            "price_chart": price_chart,
            "vol_chart": vol_chart,
            "oi_chart": oi_chart,
        }

    saved = st.session_state.get(f"{key}_plot", None)
    if saved:
        st.success(f"Strike {saved['strike']} | {saved['opt_type']}")
        plot_metric("lastPrice", "Price", df, saved["strike"], saved["opt_type"], saved["price_chart"], color)
        plot_metric("volChange", "ΔVolume", df, saved["strike"], saved["opt_type"], saved["vol_chart"], color)
        plot_metric("oiChange", "ΔOI (per strike)", df, saved["strike"], saved["opt_type"], saved["oi_chart"], color)

# -----------------------------------------
# Layout: Panel A then B (green)
# -----------------------------------------
panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")
