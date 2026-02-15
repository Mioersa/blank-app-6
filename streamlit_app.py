import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Robust Strike Finder · Dual Panels)")

# ---------------------------------------------------------------------
# FILE UPLOAD + CLEAR
# ---------------------------------------------------------------------
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = None

if st.button("🗑️ Clear uploaded files"):
    st.session_state.clear()
    st.experimental_rerun()

uploaded = st.file_uploader(
    "Upload one or more CSV files (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)
if uploaded:
    st.session_state["uploaded_files"] = uploaded

files = st.session_state.get("uploaded_files", [])
if not files:
    st.info("👆 Upload CSVs to begin")
    st.stop()

# ---------------------------------------------------------------------
# 1️⃣  READ FILES SAFELY
# ---------------------------------------------------------------------
frames = []
valid_files = []

for f in files:
    try:
        df = pd.read_csv(f)
        # guard: pandas can return EmptyDataError OR df.shape=(0,0)
        if df.empty or df.shape[1] == 0:
            st.warning(f"⚠️ Skipped: {f.name} (empty / no columns)")
            continue
        df.columns = [c.strip().replace(" ", "_") for c in df.columns]
        valid_files.append((f, df))
        frames.append(df)
    except Exception as e:
        st.warning(f"⚠️ Skipped {f.name}: {e}")

if not frames:
    st.error("❌ No valid CSVs found.")
    st.stop()

# combine all
df = pd.concat(frames, ignore_index=True)
df = df.loc[:, ~df.columns.duplicated()]

# ---------------------------------------------------------------------
# 2️⃣  STRIKE COLUMN FROM FIRST VALID FILE
# ---------------------------------------------------------------------
first_name, first_df = valid_files[0]
strike_cols = [c for c in first_df.columns if re.search("strike", c, re.IGNORECASE)]

if not strike_cols:
    st.error("No 'strike' column found in first file.")
    st.write("Detected:", first_df.columns.tolist())
    st.stop()

strike_col = strike_cols[0]

# dropdown values
try:
    strike_values = (
        pd.to_numeric(first_df[strike_col], errors="coerce").dropna().unique()
    )
    strike_values = sorted(strike_values)
except Exception:
    strike_values = sorted(first_df[strike_col].dropna().unique())

if not len(strike_values):
    st.error(f"No valid entries in `{strike_col}` of {first_name.name}")
    st.stop()

selected_strike = st.selectbox(
    f"Select strike value from `{strike_col}` of {first_name.name}", strike_values
)
st.markdown("---")

# ---------------------------------------------------------------------
# 3️⃣  TIMESTAMP PARSER
# ---------------------------------------------------------------------
def parse_filename(name):
    m = re.search(r"(\d{2})(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None, None
    d, mo, y, h, mi, s = m.groups()
    return f"{d}-{mo}-{y} {h}:{mi}:{s}", f"T{h}{mi}"

# ensure timestamp/time_label exist
if "timestamp" not in df.columns:
    df["timestamp"], df["time_label"] = None, None

# ---------------------------------------------------------------------
# 4️⃣  OPTIONAL CALC ΔVOLUME / ΔOI
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
# 5️⃣  PLOT HELPER
# ---------------------------------------------------------------------
def plot_metric(metric, label, df, strike, opt_type, chart_type, color=None):
    prefixes = ["CE_", "PE_"] if opt_type == "Both" else [f"{opt_type}_"]

    for pre in prefixes:
        col, s_col = f"{pre}{metric}", f"{pre}strikePrice"
        if col not in df.columns or s_col not in df.columns:
            continue

        tmp = df[df[s_col] == strike].copy()
        if tmp.empty:
            continue

        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0)
        tmp["time_label"] = tmp.get("time_label", range(len(tmp)))

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
            xaxis_title="Time (HHMM)",
            yaxis_title=label,
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------
# 6️⃣  PANEL
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
# 7️⃣  LAYOUT
# ---------------------------------------------------------------------
panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")
