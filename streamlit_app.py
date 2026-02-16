import streamlit as st
import pandas as pd
import plotly.express as px
import re
from io import StringIO

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Δ‑Metrics + Correlations)")

# -----------------------------------------
# File upload
# -----------------------------------------
files = st.file_uploader(
    "Upload multiple CSVs (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"],
    accept_multiple_files=True,
)
if not files:
    st.info("👆 Upload option‑chain CSVs to start")
    st.stop()

def parse_time(name):
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return None, None
    d, mo, y, h, mi, s = m.groups()
    return f"{d}-{mo}-{y} {h}:{mi}:{s}", f"{h}{mi}"

frames = []
for f in files:
    df = pd.read_csv(f)
    full, short = parse_time(f.name)
    df["timestamp"] = full
    df["time_label"] = short
    frames.append(df)

df = pd.concat(frames)
df.dropna(subset=["timestamp"], inplace=True)
df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
df = df.sort_values("timestamp").reset_index(drop=True)

# -----------------------------------------
# Per‑strike deltas
# -----------------------------------------
for pre in ["CE_", "PE_"]:
    cols = [
        f"{pre}totalTradedVolume",
        f"{pre}openInterest",
        f"{pre}lastPrice",
        f"{pre}impliedVolatility",
        f"{pre}strikePrice",
    ]
    if not all(c in df.columns for c in cols):
        continue
    vol, oi, price, iv, strike = cols

    def add_deltas(g):
        g = g.sort_values("timestamp")
        g[f"{pre}volChange"] = g[vol].diff().fillna(0)
        g[f"{pre}oiChange"] = g[oi].diff().fillna(0)
        g[f"{pre}priceChange"] = g[price].diff().fillna(0)
        g[f"{pre}ivChange"] = g[iv].diff().fillna(0)
        g[f"{pre}pctReturn"] = g[price].pct_change().fillna(0) * 100
        return g

    df = df.groupby(strike, group_keys=False).apply(add_deltas)

# OI imbalance and Put/Call ratio
if {"CE_openInterest", "PE_openInterest"}.issubset(df.columns):
    df["OI_imbalance"] = (df["CE_openInterest"] - df["PE_openInterest"]) / (
        df["CE_openInterest"] + df["PE_openInterest"] + 1e-9
    )
if {"CE_totalTradedVolume", "PE_totalTradedVolume"}.issubset(df.columns):
    df["PCR"] = df["PE_totalTradedVolume"] / (df["CE_totalTradedVolume"] + 1e-9)

# -----------------------------------------
# Generic plotter
# -----------------------------------------
def plot_metric(metric, label, df, strike, opt_type, style, color=None):
    prefixes = ["CE_", "PE_"] if opt_type == "Both" else [f"{opt_type}_"]
    for pre in prefixes:
        col = f"{pre}{metric}"
        s_col = f"{pre}strikePrice"
        if col not in df.columns:
            continue
        tmp = df[df[s_col] == strike].sort_values("timestamp")
        if tmp.empty:
            continue
        tmp["time_label"] = tmp["time_label"].astype(str)
        tmp["x_idx"] = range(len(tmp))
        fig = px.line(tmp, x="x_idx", y=col, markers=(style == "Line")) if style == "Line" else px.bar(tmp, x="x_idx", y=col)
        if color:
            fig.update_traces(marker_color=color, line_color=color)
        fig.update_layout(
            title=f"{pre}{label}",
            height=400,
            xaxis=dict(
                tickmode="array",
                tickvals=list(tmp["x_idx"]),
                ticktext=[f"T{t}" for t in tmp["time_label"]],
                tickangle=-45,
            ),
            yaxis_title=label,
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------
# Panels A/B
# -----------------------------------------
def panel(name, color=None):
    st.subheader(name)
    strikes = []
    if "CE_strikePrice" in df.columns:
        strikes = sorted(pd.to_numeric(df["CE_strikePrice"], errors="coerce").dropna().unique())
    elif "PE_strikePrice" in df.columns:
        strikes = sorted(pd.to_numeric(df["PE_strikePrice"], errors="coerce").dropna().unique())
    if not strikes:
        st.warning("No strikes detected.")
        return
    strike = st.selectbox(f"{name} Strike", strikes, key=f"{name}_strike")
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{name}_opt", horizontal=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        p_style = st.radio("Price", ["Line", "Bar"], key=f"{name}_p")
    with c2:
        v_style = st.radio("ΔVolume", ["Line", "Bar"], key=f"{name}_v")
    with c3:
        o_style = st.radio("ΔOI", ["Line", "Bar"], key=f"{name}_o")
    if st.button("Plot", key=f"{name}_btn"):
        st.session_state[f"{name}_plot"] = dict(strike=strike, opt=opt_type, p=p_style, v=v_style, o=o_style)
    saved = st.session_state.get(f"{name}_plot")
    if saved:
        st.success(f"{saved['opt']} | Strike {saved['strike']}")
        plot_metric("lastPrice", "Price", df, saved["strike"], saved["opt"], saved["p"], color)
        plot_metric("volChange", "ΔVolume", df, saved["strike"], saved["opt"], saved["v"], color)
        plot_metric("oiChange", "ΔOI (per strike)", df, saved["strike"], saved["opt"], saved["o"], color)

panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")

# -----------------------------------------
# Panel C — Δ‑Metric Correlation w/ Relations text
# -----------------------------------------
st.markdown("---")
st.subheader("📈 Panel C – Δ Metric Correlation (ΔPrice, ΔVol, ΔOI, ΔIV)")

strikes = sorted(pd.to_numeric(df.get("CE_strikePrice", df.get("PE_strikePrice", pd.Series())), errors="coerce").dropna().unique())
if not strikes:
    st.warning("No strike data.")
    st.stop()

strike = st.selectbox("Strike (Correlation view)", strikes)
min_t, max_t = df["timestamp"].min().to_pydatetime(), df["timestamp"].max().to_pydatetime()
t_start, t_end = st.slider("Time Range", min_value=min_t, max_value=max_t, value=(min_t, max_t), format="HH:mm")
df_rng = df[(df["timestamp"] >= t_start) & (df["timestamp"] <= t_end)]

corr_frames = []
for pre in ["CE_", "PE_"]:
    needed = [f"{pre}{x}" for x in ["volChange", "priceChange", "oiChange", "ivChange"]]
    existing = [c for c in needed if c in df_rng.columns]
    tmp = df_rng[df_rng[f"{pre}strikePrice"] == strike][existing].dropna()
    if tmp.empty:
        continue
    tmp.columns = [c.replace(pre, "") + f"_{pre[:-1]}" for c in tmp.columns]
    corr_frames.append(tmp.reset_index(drop=True))

if not corr_frames:
    st.warning("No Δ‑metrics to correlate.")
else:
    merged = pd.concat(corr_frames, axis=1)
    corr = merged.corr().round(2)
    st.dataframe(corr)

    fig = px.imshow(corr, text_auto=True, color_continuous_scale="RdYlGn",
                    title=f"Correlation Matrix – Strike {strike}")
    st.plotly_chart(fig, use_container_width=True)

    # --- Insight summary
    threshold = 0.5
    insights = []
    for a in corr.columns:
        for b in corr.columns:
            if a == b:
                continue
            val = corr.loc[a, b]
            if abs(val) >= threshold:
                direction = "positively" if val > 0 else "negatively"
                strength = "strongly" if abs(val) >= 0.7 else "moderately"
                insights.append(
                    f"• Change in **{a.replace('_',' ')}** is {strength} {direction} related to change in **{b.replace('_',' ')}** (ρ = {val:.2f})"
                )
    if insights:
        st.markdown("### 🔍 Relation Insights")
        st.markdown("\n".join(sorted(set(insights))))
    else:
        st.info("No meaningful relations (|ρ| ≥ 0.5) detected.")

    # CSV export
    buff = StringIO()
    corr.to_csv(buff)
    st.download_button("📥 Download correlation CSV", buff.getvalue(), f"correlation_{strike}.csv")
