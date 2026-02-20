import streamlit as st
import pandas as pd
import plotly.express as px
import re
from io import StringIO

st.set_page_config(page_title="Options Data Viewer", layout="wide")
st.title("📊 Options Data Viewer (Δ‑Metrics + Correlations + Strength)")

# -----------------------------------------
# Upload CSVs
# -----------------------------------------
files = st.file_uploader(
    "Upload multiple CSVs (_DDMMYYYY_HHMMSS.csv)",
    type=["csv"], accept_multiple_files=True,
)
if not files:
    st.info("👆 Upload option‑chain CSVs to start")
    st.stop()

def parse_time(name):
    m = re.search(r"_(\d{2})(\d{2})(\d{4})_(\d{2})(\d{2})(\d{2})", name)
    if not m: return None, None
    d, mo, y, h, mi, s = m.groups()
    return f"{d}-{mo}-{y} {h}:{mi}:{s}", f"{h}{mi}"

frames=[]
for f in files:
    d=pd.read_csv(f)
    full,short=parse_time(f.name)
    d["timestamp"]=full; d["time_label"]=short
    frames.append(d)
df=pd.concat(frames)
df.dropna(subset=["timestamp"],inplace=True)
df["timestamp"]=pd.to_datetime(df["timestamp"],format="%d-%m-%Y %H:%M:%S",errors="coerce")
df=df.sort_values("timestamp").reset_index(drop=True)

# -----------------------------------------
# Calculate deltas
# -----------------------------------------
for pre in ["CE_","PE_"]:
    cols=[f"{pre}totalTradedVolume",f"{pre}openInterest",f"{pre}lastPrice",f"{pre}impliedVolatility",f"{pre}strikePrice"]
    if not all(c in df.columns for c in cols): continue
    vol,oi,price,iv,strike=cols
    def add_d(g):
        g=g.sort_values("timestamp")
        g[f"{pre}volChange"]=g[vol].diff().fillna(0)
        g[f"{pre}oiChange"]=g[oi].diff().fillna(0)
        g[f"{pre}priceChange"]=g[price].diff().fillna(0)
        g[f"{pre}ivChange"]=g[iv].diff().fillna(0)
        return g
    df=df.groupby(strike,group_keys=False).apply(add_d)

# derived extras
if {"CE_openInterest","PE_openInterest"}.issubset(df.columns):
    df["OI_imbalance"]=(df["CE_openInterest"]-df["PE_openInterest"])/(df["CE_openInterest"]+df["PE_openInterest"]+1e-9)

# -----------------------------------------
# Plot helper
# -----------------------------------------
def plot_metric(metric,label,df,strike,opt_type,style,color=None):
    prefixes=["CE_","PE_"] if opt_type=="Both" else [f"{opt_type}_"]
    for pre in prefixes:
        col=f"{pre}{metric}"; s_col=f"{pre}strikePrice"
        if col not in df.columns: continue
        tmp=df[df[s_col]==strike].sort_values("timestamp")
        if tmp.empty: continue
        tmp["x"]=range(len(tmp))
        if style=="Line":
            fig=px.line(tmp,x="x",y=col,title=f"{pre}{label}",markers=True)
        else:
            fig=px.bar(tmp,x="x",y=col,title=f"{pre}{label}")
        # ---- fixed color handling ----
        if color:
            update_args=dict(marker_color=color)
            if style=="Line":
                update_args["line_color"]=color
            fig.update_traces(**update_args)
        # -------------------------------
        fig.update_layout(
            height=400,
            xaxis=dict(
                ticktext=[f"T{t}" for t in tmp["time_label"]],
                tickvals=tmp["x"],
                tickangle=-45,
            ),
            yaxis_title=label,
        )
        st.plotly_chart(fig,use_container_width=True)

# -----------------------------------------
# Panels A/B
# -----------------------------------------
def panel(name,color=None):
    st.subheader(name)
    strikes=[]
    if "CE_strikePrice" in df.columns: strikes=sorted(pd.to_numeric(df["CE_strikePrice"],errors="coerce").dropna().unique())
    elif "PE_strikePrice" in df.columns: strikes=sorted(pd.to_numeric(df["PE_strikePrice"],errors="coerce").dropna().unique())
    if not strikes: st.warning("No strikes detected."); return
    strike=st.selectbox(f"{name} Strike",strikes,key=f"{name}_strike")
    opt=st.radio("Option Type",["CE","PE","Both"],key=f"{name}_opt",horizontal=True)
    c1,c2,c3=st.columns(3)
    with c1: p=st.radio("Price",["Line","Bar"],key=f"{name}_p")
    with c2: v=st.radio("ΔVolume",["Line","Bar"],key=f"{name}_v")
    with c3: o=st.radio("ΔOI",["Line","Bar"],key=f"{name}_o")
    if st.button("Plot",key=f"{name}_btn"):
        st.session_state[f"{name}_plot"]=dict(s=strike,o=opt,p=p,v=v,oi=o)
    saved=st.session_state.get(f"{name}_plot")
    if saved:
        st.success(f"{saved['o']} | Strike {saved['s']}")
        plot_metric("lastPrice","Price",df,saved["s"],saved["o"],saved["p"],color)
        plot_metric("volChange","ΔVolume",df,saved["s"],saved["o"],saved["v"],color)
        plot_metric("oiChange","ΔOI (per strike)",df,saved["s"],saved["o"],saved["oi"],color)

panel("Panel A"); st.markdown("---"); panel("Panel B",color="green")

# -----------------------------------------
# Panel C – Detailed + Comparison
# -----------------------------------------
st.markdown("---")
st.subheader("📈 Panel C – Intra‑Side Δ‑Correlations (ΔPrice vs ΔVol/ΔOI/ΔIV)")
strikes=sorted(pd.to_numeric(df.get("CE_strikePrice",df.get("PE_strikePrice",pd.Series())),errors="coerce").dropna().unique())
if not strikes: st.warning("No strikes available.")
else:
    strike=st.selectbox("Strike (Relation check)",strikes)
    min_t,max_t=df["timestamp"].min().to_pydatetime(),df["timestamp"].max().to_pydatetime()
    t1,t2=st.slider("Select time range",min_value=min_t,max_value=max_t,value=(min_t,max_t),format="HH:mm")
    df_r=df[(df["timestamp"]>=t1)&(df["timestamp"]<=t2)]
    st.markdown(f"### Strike {strike} | {t1.strftime('%H:%M')}–{t2.strftime('%H:%M')}")

    def details(prefix,label_emoji):
        cols=[f"{prefix}{x}" for x in ["priceChange","volChange","oiChange","ivChange"]]
        if not all(c in df_r.columns for c in cols): return {}
        d=df_r[df_r[f"{prefix}strikePrice"]==strike].dropna(subset=cols)
        if d.empty: return {}
        out,lines={},[]
        pairs={"ΔVolume":"volChange","ΔOI":"oiChange","ΔIV":"ivChange"}
        for lbl,c2 in pairs.items():
            val=d[f"{prefix}priceChange"].corr(d[f"{prefix}{c2}"])
            if pd.notna(val):
                out[lbl]=val
                direction="positively" if val>0 else "negatively"
                strength="strongly" if abs(val)>=0.7 else "moderately" if abs(val)>=0.4 else "weakly"
                lines.append(f"{label_emoji} ΔPrice vs {lbl} → {strength} {direction} correlated (ρ = {val:.2f})")
        for line in lines: st.write(line)
        return out

    ce_corr=details("CE_","🟢 CE‑side")
    pe_corr=details("PE_","🔴 PE‑side")

    compare=[]
    for lbl in ["ΔVolume","ΔOI","ΔIV"]:
        c=ce_corr.get(lbl); p=pe_corr.get(lbl)
        if pd.notna(c) and pd.notna(p):
            stronger="🟢 CE stronger" if abs(c)>abs(p) else "🔴 PE stronger"
            compare.append(f"{lbl}: CE ρ = {c:.2f} | PE ρ = {p:.2f} → **{stronger}**")
    if compare:
        st.markdown("**➡ Comparative Summary (CE vs PE)**")
        st.markdown("\n".join(compare))

# -----------------------------------------
# Panel D – Composite Strength Score
# -----------------------------------------
st.markdown("---")
st.subheader("💪 Panel D – Composite Strength Score (CE vs PE)")
results=[]
strikes=sorted(pd.to_numeric(df.get("CE_strikePrice",df.get("PE_strikePrice",pd.Series())),errors="coerce").dropna().unique())
for s in strikes:
    row={"Strike":s}
    for side in ["CE_","PE_"]:
        if f"{side}priceChange" not in df.columns: continue
        d=df[df[f"{side}strikePrice"]==s]
        if d.empty: continue
        r_oi=d[f"{side}priceChange"].corr(d[f"{side}oiChange"])
        r_vol=d[f"{side}priceChange"].corr(d[f"{side}volChange"])
        oi_imb=d["OI_imbalance"].mean() if "OI_imbalance" in d else 0
        row[f"{side[:-1]}_Strength"]=0.4*(r_oi or 0)+0.3*(r_vol or 0)+0.3*oi_imb
    results.append(row)

if results:
    out=pd.DataFrame(results)
    out["Bias"]=out.apply(lambda r:"Bullish" if r.get("CE_Strength",0)>r.get("PE_Strength",0) else "Bearish",axis=1)
    bias_colors={"Bullish":"#ccffcc","Bearish":"#ffcccc"}
    def color_bias(v): return f"background-color:{bias_colors.get(v,'')}"
    st.dataframe(out.style.applymap(color_bias,subset=["Bias"]).format(precision=3))

    overall = ("🟢 Overall Bias = CE (Bullish)"
               if out["CE_Strength"].mean()>out["PE_Strength"].mean()
               else "🔴 Overall Bias = PE (Bearish)")
    st.markdown(f"### {overall}")

    fig=px.bar(out,x="Strike",y=["CE_Strength","PE_Strength"],barmode="group",
               title="Composite Strength (CE vs PE)")
    st.plotly_chart(fig,use_container_width=True)
else:
    st.info("No valid strength data yet.")
