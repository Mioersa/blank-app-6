import streamlit as st
import pandas as pd
import plotly.express as px
import re
from io import StringIO

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (HHMM labels, stable Bar/Line)")

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

        fig_func = px.line if chart_type == "Line" else px.bar
        fig = fig_func(tmp, x="x_index", y=col, title=f"{pre}{label}", markers=(chart_type == "Line"))

        if color:
            if chart_type == "Line":
                fig.update_traces(line_color=color, marker_color=color)
            else:
                fig.update_traces(marker_color=color)

        tick_texts = [f"T{t}" for t in tmp["time_label"]]
        fig.update_layout(
            height=400,
            xaxis_title="Time (HHMM)",
            yaxis_title=label,
            xaxis=dict(
                tickmode="array",
                tickvals=list(tmp["x_index"]),
                ticktext=tick_texts,
                tickangle=-45,
                tickfont=dict(size=10),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        csv_buffer = StringIO()
        tmp.to_csv(csv_buffer, index=False)
        st.download_button(
            label=f"📥 Download {pre}{label} data (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"{pre}{metric}_{strike}_{chart_type}.csv",
            mime="text/csv",
        )

# -----------------------------------------
# Panels A and B
# -----------------------------------------
def panel(name, color=None):
    st.subheader(name)
    key = name.replace(" ", "_")
    strike_list = []
    if "CE_strikePrice" in df.columns:
        strike_list = sorted(pd.to_numeric(df["CE_strikePrice"], errors="coerce").dropna().unique().tolist())
    elif "PE_strikePrice" in df.columns:
        strike_list = sorted(pd.to_numeric(df["PE_strikePrice"], errors="coerce").dropna().unique().tolist())

    if not strike_list:
        st.warning("No strikes detected in data.")
        return

    strike = st.selectbox(f"{name} Strike", strike_list, key=f"{key}_strike")
    opt_type = st.radio("Option Type", ["CE", "PE", "Both"], key=f"{key}_type", horizontal=True)

    st.markdown("**Chart Types (per metric)**")
    c1, c2, c3 = st.columns(3)
    with c1:
        price_chart = st.radio("Price", ["Line", "Bar"], key=f"{key}_p", horizontal=True)
    with c2:
        vol_chart = st.radio("ΔVolume", ["Line", "Bar"], key=f"{key}_v", horizontal=True)
    with c3:
        oi_chart = st.radio("ΔOI", ["Line", "Bar"], key=f"{key}_o", horizontal=True)

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
        st.success(f"{saved['opt_type']} | Strike {saved['strike']}")
        plot_metric("lastPrice", "Price", df, saved["strike"], saved["opt_type"], saved["price_chart"], color)
        plot_metric("volChange", "ΔVolume", df, saved["strike"], saved["opt_type"], saved["vol_chart"], color)
        plot_metric("oiChange", "ΔOI (per strike)", df, saved["strike"], saved["opt_type"], saved["oi_chart"], color)

panel("Panel A")
st.markdown("---")
panel("Panel B", color="green")

# -----------------------------------------
# Panel C – Correlation with time slider
# -----------------------------------------
st.markdown("---")
st.subheader("📈 Panel C – Δ‑Metric Correlation (Price Δ / Vol Δ / OI Δ / IV Δ | CE + PE)")

strike_list = []
if "CE_strikePrice" in df.columns:
    strike_list = sorted(pd.to_numeric(df["CE_strikePrice"], errors="coerce").dropna().unique().tolist())
elif "PE_strikePrice" in df.columns:
    strike_list = sorted(pd.to_numeric(df["PE_strikePrice"], errors="coerce").dropna().unique().tolist())

if not strike_list:
    st.warning("No strikes detected.")
else:
    strike = st.selectbox("Strike (Correlation view)", strike_list)

    # slider on timestamp
    min_t, max_t = df["timestamp"].min(), df["timestamp"].max()
    t_range = st.slider("Select time range for correlation", min_t, max_t, (min_t, max_t), format="HH:mm")

    df_range = df[(df["timestamp"] >= pd.to_datetime(t_range[0])) & (df["timestamp"] <= pd.to_datetime(t_range[1]))]

    corr_frames = []
    for pre in ["CE_", "PE_"]:
        needed = [
            f"{pre}volChange",
            f"{pre}priceChange",
            f"{pre}oiChange",
            f"{pre}ivChange",
        ]
        exist = [c for c in needed if c in df_range.columns]
        if len(exist) < 2:
            continue
        tmp = df_range[df_range[f"{pre}strikePrice"] == strike][exist].copy()
        if not tmp.empty:
            tmp.columns = [c.replace(pre, "") + f"_{pre[:-1]}" for c in tmp.columns]
            corr_frames.append(tmp.reset_index(drop=True))

    if not corr_frames:
        st.warning("Not enough columns for correlation.")
    else:
        merged = pd.concat(corr_frames, axis=1)
        corr = merged.corr().round(2)

        st.write(f"Correlation | Strike {strike} | {t_range[0].strftime('%H:%M')}–{t_range[1].strftime('%H:%M')}")
        st.dataframe(corr)

        fig = px.imshow(
            corr,
            text_auto=True,
            color_continuous_scale="RdYlGn",
            title=f"Δ‑Metric Correlation ({strike})",
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

        csv_buffer = StringIO()
        corr.to_csv(csv_buffer)
        st.download_button(
            label=f"📥 Download correlation ({strike}).csv",
            data=csv_buffer.getvalue(),
            file_name=f"correlation_{strike}.csv",
            mime="text/csv",
        )
