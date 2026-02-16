import streamlit as st
import pandas as pd
import plotly.express as px
import re
from io import StringIO

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Δ‑Metrics + Correlations + Strength)")

# -----------------------------------------
# File Upload
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
# ΔVolume / ΔOI / ΔPrice / ΔIV per strike
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

# --- OI imbalance + Put/Call ratio
if {"CE_openInterest", "PE_openInterest"}.issubset(df.columns):
    df["OI_imbalance"] = (df["CE_openInterest"] - df["PE_openInterest"]) / (
        df["CE_openInterest"] + df["PE_openInterest"] + 1e-9
    )
if {"CE_totalTradedVolume", "PE_totalTradedVolume"}.issubset(df.columns):
    df["PCR"] = df["PE_totalTradedVolume"] / (df["CE_totalTradedVolume"] + 1e-9)

# -----------------------------------------
# Plot helper
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
        if style == "Line":
            fig = px.line(tmp, x="x_idx", y=col, title=f"{pre}{label}", markers=True)
        else:
            fig = px.bar(tmp, x="x_idx", y=col, title=f"{pre}{label}")
        if color:
            fig.update_traces(marker_color=color, line_color=color)
        fig.update_layout(
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
# Panel A/B
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
        st.success(f"{saved['opt']} | Strike {saved['strike']}")
        plot_metric("lastPrice", "Price", df, saved["strike"], saved["opt"], saved["p"], color)
        plot_metric("volChange", "ΔVolume", df, saved["strike"], saved["opt"], saved["v"], color)
        plot_metric("oiChange", "ΔOI (per strike)", df, saved["strike"], saved["opt"], saved["o"], color)

panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")

# -----------------------------------------
# Panel C – Intra‑Side Δ‑Correlations
# -----------------------------------------
st.markdown("---")
st.subheader("📈 Panel C – Intra‑Side Δ‑Correlations (ΔPrice vs ΔVol/ΔOI/ΔIV)")

strikes = sorted(
    pd.to_numeric(df.get("CE_strikePrice", df.get("PE_strikePrice", pd.Series())), errors="coerce").dropna().unique()
)
if not strikes:
    st.warning("No strikes available.")
else:
    strike = st.selectbox("Strike (Relation check)", strikes)
    min_t, max_t = df["timestamp"].min().to_pydatetime(), df["timestamp"].max().to_pydatetime()
    t_start, t_end = st.slider(
        "Select time range",
        min_value=min_t,
        max_value=max_t,
        value=(min_t, max_t),
        format="HH:mm",
    )
    df_range = df[(df["timestamp"] >= t_start) & (df["timestamp"] <= t_end)]
    st.markdown(f"### Strike {strike} | {t_start.strftime('%H:%M')} → {t_end.strftime('%H:%M')}")

    def summarize_side(prefix, label_color):
        cols = [f"{prefix}{x}" for x in ["priceChange", "volChange", "oiChange", "ivChange"]]
        if not all(c in df_range.columns for c in cols):
            return []
        d = df_range[df_range[f"{prefix}strikePrice"] == strike].dropna(subset=cols)
        if d.empty:
            return []
        rels = []
        pairs = {
            "ΔPrice vs ΔVolume": ("priceChange", "volChange"),
            "ΔPrice vs ΔOI": ("priceChange", "oiChange"),
            "ΔPrice vs ΔIV": ("priceChange", "ivChange"),
        }
        for name, (a, b) in pairs.items():
            val = d[f"{prefix}{a}"].corr(d[f"{prefix}{b}"])
            if pd.notna(val):
                direction = "positively" if val > 0 else "negatively"
                strength = "strongly" if abs(val) >= 0.7 else "moderately" if abs(val) >= 0.4 else "weakly"
                rels.append(
                    f"{label_color} {name} → {strength} {direction} correlated (ρ = {val:.2f})"
                )
        return rels

    ce_lines = summarize_side("CE_", "🟢 CE‑side")
    pe_lines = summarize_side("PE_", "🔴 PE‑side")

    if (not ce_lines) and (not pe_lines):
        st.info("No sufficient Δ‑data for correlations.")
    else:
        if ce_lines:
            st.markdown("\n".join(ce_lines))
        if pe_lines:
            st.markdown("\n".join(pe_lines))

# -----------------------------------------
# Panel D – Composite Strength (CE vs PE)
# -----------------------------------------
st.markdown("---")
st.subheader("💪 Panel D – Composite Strength Score (CE vs PE)")

results = []
strikes = sorted(
    pd.to_numeric(df.get("CE_strikePrice", df.get("PE_strikePrice", pd.Series())), errors="coerce").dropna().unique()
)
for strike in strikes:
    row = {"Strike": strike}
    for side in ["CE_", "PE_"]:
        if f"{side}priceChange" not in df.columns:
            continue
        d = df[df[f"{side}strikePrice"] == strike]
        if d.empty:
            continue
        r_price_oi = d[f"{side}priceChange"].corr(d[f"{side}oiChange"])
        r_price_vol = d[f"{side}priceChange"].corr(d[f"{side}volChange"])
        oi_imb = d["OI_imbalance"].mean() if "OI_imbalance" in d else 0
        row[f"{side[:-1]}_Strength"] = (
            0.4 * (r_price_oi or 0) + 0.3 * (r_price_vol or 0) + 0.3 * oi_imb
        )
    results.append(row)

if results:
    out = pd.DataFrame(results)
    out["Bias"] = out.apply(
        lambda r: "Bull" if r.get("CE_Strength", 0) > r.get("PE_Strength", 0) else "Bear",
        axis=1,
    )
    st.dataframe(out.round(3))
    fig = px.bar(out, x="Strike", y=["CE_Strength", "PE_Strength"], barmode="group",
                 title="Composite Strength (CE vs PE)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No valid strength data yet.")
