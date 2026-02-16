import streamlit as st
import pandas as pd
import plotly.express as px
import re
from io import StringIO
from datetime import time

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Δ‑Metrics + Correlation)")

# -----------------------------------------
# Upload CSVs
# -----------------------------------------
files = st.file_uploader(
    "Upload multiple CSVs (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)
if not files:
    st.info("👆 Upload option‑chain CSVs to start")
    st.stop()

def get_time_from_filename(name):
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None, None
    d, mo, y, h, mi, s = m.groups()
    full = f"{d}-{mo}-{y} {h}:{mi}:{s}"
    short = f"{h}{mi}"
    return full, short

# -----------------------------------------
# Combine uploaded CSVs
# -----------------------------------------
frames = []
for f in files:
    df = pd.read_csv(f)
    full, short = get_time_from_filename(f.name)
    df["timestamp"] = full
    df["time_label"] = short
    frames.append(df)

df = pd.concat(frames)
df.dropna(subset=["timestamp"], inplace=True)
df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
df = df.sort_values("timestamp").reset_index(drop=True)

# -----------------------------------------
# ΔVolume / ΔOI / ΔPrice / ΔIV per strike
# -----------------------------------------
for prefix in ["CE_", "PE_"]:
    cols = [f"{prefix}totalTradedVolume", f"{prefix}openInterest", f"{prefix}lastPrice", f"{prefix}impliedVolatility", f"{prefix}strikePrice"]
    if not all(c in df.columns for c in cols):
        continue
    vol_col, oi_col, price_col, iv_col, strike_col = cols

    def add_deltas(g):
        g = g.sort_values("timestamp")
        g[f"{prefix}volChange"] = g[vol_col].diff().fillna(0)
        g[f"{prefix}oiChange"] = g[oi_col].diff().fillna(0)
        g[f"{prefix}priceChange"] = g[price_col].diff().fillna(0)
        g[f"{prefix}ivChange"] = g[iv_col].diff().fillna(0)
        return g

    df = df.groupby(strike_col, group_keys=False).apply(add_deltas)

# -----------------------------------------
# Plot helper
# -----------------------------------------
def plot_metric(metric, label, df, strike, opt_type, chart_type, color=None):
    prefixes = ["CE_", "PE_"] if opt_type == "Both" else [f"{opt_type}_"]
    for pre in prefixes:
        col = f"{pre}{metric}"
        strike_col = f"{pre}strikePrice"
        if col not in df.columns or strike_col not in df.columns:
            continue

        tmp = df[df[strike_col] == strike].copy().sort_values("timestamp")
        if tmp.empty:
            continue

        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0)
        tmp["time_label"] = tmp["time_label"].astype(str)
        tmp["x_index"] = range(len(tmp))

        # ✅ chart creation fix
        if chart_type == "Line":
            fig = px.line(tmp, x="x_index", y=col, title=f"{pre}{label}", markers=True)
        else:
            fig = px.bar(tmp, x="x_index", y=col, title=f"{pre}{label}")

        if color:
            fig.update_traces(line_color=color, marker_color=color)

        fig.update_layout(
            height=400,
            xaxis_title="Time (HHMM)",
            yaxis_title=label,
            xaxis=dict(
                tickmode="array",
                tickvals=list(tmp["x_index"]),
                ticktext=[f"T{t}" for t in tmp["time_label"]],
                tickangle=-45,
                tickfont=dict(size=10),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        buff = StringIO()
        tmp.to_csv(buff, index=False)
        st.download_button(
            label=f"📥 Download {pre}{label} CSV",
            data=buff.getvalue(),
            file_name=f"{pre}{metric}_{strike}.csv",
            mime="text/csv",
        )

# -----------------------------------------
# Panels A/B
# -----------------------------------------
def panel(name, color=None):
    st.subheader(name)
    key = name.replace(" ", "_")
    strikes = []
    if "CE_strikePrice" in df.columns:
        strikes = sorted(pd.to_numeric(df["CE_strikePrice"], errors="coerce").dropna().unique())
    elif "PE_strikePrice" in df.columns:
        strikes = sorted(pd.to_numeric(df["PE_strikePrice"], errors="coerce").dropna().unique())

    if not strikes.any():
        st.warning("No strikes detected.")
        return

    strike = st.selectbox(f"{name} Strike", strikes, key=f"{key}_strike")
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key}_type", horizontal=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        price_chart = st.radio("Price", ["Line", "Bar"], key=f"{key}_p", horizontal=True)
    with c2:
        vol_chart = st.radio("ΔVolume", ["Line", "Bar"], key=f"{key}_v", horizontal=True)
    with c3:
        oi_chart = st.radio("ΔOI", ["Line", "Bar"], key=f"{key}_o", horizontal=True)

    if st.button("Plot", key=f"{key}_btn"):
        st.session_state[f"{key}_plot"] = dict(
            strike=strike,
            opt_type=opt_type,
            price_chart=price_chart,
            vol_chart=vol_chart,
            oi_chart=oi_chart,
        )

    saved = st.session_state.get(f"{key}_plot")
    if saved:
        st.success(f"{saved['opt_type']} | Strike {saved['strike']}")
        plot_metric("lastPrice", "Price", df, saved["strike"], saved["opt_type"], saved["price_chart"], color)
        plot_metric("volChange", "ΔVolume", df, saved["strike"], saved["opt_type"], saved["vol_chart"], color)
        plot_metric("oiChange", "ΔOI (per strike)", df, saved["strike"], saved["opt_type"], saved["oi_chart"], color)

panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")

# -----------------------------------------
# Panel C – Δ‑Metric Correlation with Time Slider
# -----------------------------------------
st.markdown("---")
st.subheader("📈 Panel C – Δ‑Metric Correlation (ΔPrice / ΔIV / ΔVol / ΔOI)")

if "CE_strikePrice" in df.columns:
    strikes = sorted(pd.to_numeric(df["CE_strikePrice"], errors="coerce").dropna().unique())
elif "PE_strikePrice" in df.columns:
    strikes = sorted(pd.to_numeric(df["PE_strikePrice"], errors="coerce").dropna().unique())
else:
    strikes = []

if not any(strikes):
    st.warning("No strikes available.")
else:
    strike = st.selectbox("Strike (Correlation view)", strikes)
    # ✅ datetime slider fix
    min_t, max_t = df["timestamp"].min().to_pydatetime(), df["timestamp"].max().to_pydatetime()
    t_start, t_end = st.slider("Time Range",
                               min_value=min_t,
                               max_value=max_t,
                               value=(min_t, max_t),
                               format="HH:mm")
    df_slice = df[(df["timestamp"] >= t_start) & (df["timestamp"] <= t_end)]

    corr_frames = []
    for pre in ["CE_", "PE_"]:
        needed = [f"{pre}{x}" for x in ["volChange", "priceChange", "oiChange", "ivChange"]]
        existing = [c for c in needed if c in df_slice.columns]
        if not existing:
            continue
        tmp = df_slice[df_slice[f"{pre}strikePrice"] == strike][existing].copy()
        if tmp.empty:
            continue
        tmp.columns = [c.replace(pre, "") + f"_{pre[:-1]}" for c in tmp.columns]
        corr_frames.append(tmp.reset_index(drop=True))

    if not corr_frames:
        st.warning("No Δ‑metric data for correlation.")
    else:
        merged = pd.concat(corr_frames, axis=1)
        corr = merged.corr().round(2)

        st.write(f"Δ‑Metric Correlation | {t_start.strftime('%H:%M')}–{t_end.strftime('%H:%M')} | Strike {strike}")
        st.dataframe(corr)

        fig = px.imshow(corr, text_auto=True, color_continuous_scale="RdYlGn",
                        title=f"Δ‑Metric Correlation (Strike {strike})")
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

        buff = StringIO()
        corr.to_csv(buff)
        st.download_button("📥 Download correlation CSV", buff.getvalue(), f"correlation_{strike}.csv", mime="text/csv")
