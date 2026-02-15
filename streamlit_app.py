import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Auto Strike Detection + All X‑Labels)")

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
    m = re.search(r"_(\\d{2})(\\d{2})(\\d{4})_(\\d{2})(\\d{2})(\\d{2})", name)
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
# Identify strike columns dynamically
# -----------------------------------------
possible_cols = [c for c in df.columns if "strike" in c.lower()]
if not possible_cols:
    st.error("❌ No strike price column found in uploaded files.")
    st.stop()

# pick likely CE/PE versions
ce_col = next((c for c in possible_cols if "ce" in c.lower()), possible_cols[0])
pe_col = next((c for c in possible_cols if "pe" in c.lower()), possible_cols[0])

# standardize names
df.rename(columns={ce_col: "CE_strikePrice", pe_col: "PE_strikePrice"}, inplace=True, errors="ignore")

# -----------------------------------------
# Compute per‑strike ΔVolume & ΔOI
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
# Helper to get unique strikes for dropdown
# -----------------------------------------
def get_unique_strikes(df):
    cols = [c for c in df.columns if "strikePrice" in c]
    strikes = set()
    for c in cols:
        try:
            strikes |= set(pd.to_numeric(df[c], errors="coerce").dropna().unique())
        except Exception:
            pass
    return sorted(strikes)

strike_list = get_unique_strikes(df)
if not strike_list:
    st.error("❌ No strike values detected in the data.")
    st.stop()

# -----------------------------------------
# Plot helper (show all x‑labels)
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
        s_col = f"{pre}strikePrice"
        tmp = df[df[s_col] == strike].copy()
        tmp["time"] = pd.to_datetime(tmp["timestamp"], format="%d-%m-%Y %H:%M:%S")
        tmp = tmp.sort_values("time")
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0)

        x_vals = tmp["time"].tolist()
        if not len(tmp):
            st.warning(f"No data for strike {strike} in {pre}.")
            continue

        fig_func = px.line if chart_type == "Line" else px.bar
        fig = fig_func(tmp, x="time", y=col, title=f"{pre}{label}", markers=True)
        if color:
            if chart_type == "Line":
                fig.update_traces(line_color=color, marker_color=color)
            else:
                fig.update_traces(marker_color=color)

        fig.update_layout(
            height=400,
            xaxis=dict(
                tickmode="array",
                tickvals=x_vals,
                ticktext=[t.strftime("%H:%M:%S") for t in x_vals],
                ticks="outside",
                tickangle=-45,
                tickfont=dict(size=9),
            ),
            xaxis_title="Time",
            yaxis_title=label,
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------
# Panel definition
# -----------------------------------------
def panel(name, color=None):
    st.subheader(name)
    key = name.replace(" ", "_")

    strike = st.selectbox(
        f"{name} Strike",
        strike_list,
        key=f"{key}_strike"
    )
    opt_type = st.radio(
        "Option Type", ["CE", "PE", "Both"], key=f"{key}_type", horizontal=True
    )

    st.markdown("**Chart Types** (per metric):")
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
