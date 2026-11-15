import streamlit as st
import plotly.graph_objects as go
from screener import run_screening

st.set_page_config(page_title="台股波段動能選股雷達", page_icon="🎯", layout="centered")
st.title("🎯 台股波段動能選股雷達")
st.caption("可調式漲停濾網｜均線翻揚 × 溫和帶量 × 籌碼健康度")

with st.sidebar:
    st.header("⚙️ 專屬濾網參數微調")
    min_chg = st.slider("當日最低漲幅 (%)", 0.5, 8.0, 3.5, 0.5)
    max_chg = st.slider("當日最高漲幅 (% 含漲停)", 5.0, 10.5, 10.5, 0.5)
    breakout_days = st.selectbox("突破關鍵頸線天數", options=(10, 20, 60), index=1)
    use_ma_tangle = st.checkbox("啟用均線糾結發散 (選配)", value=False)
    max_tangle_pct = st.slider("5/10/20日線最大乖離 (%)", 2.0, 8.0, 5.0, 0.5)
    vol_mult = st.slider("5日均量最低倍數", 1.0, 3.0, 1.5, 0.1)
    max_vol_mult = st.slider("5日均量上限 (防爆天量)", 2.5, 8.0, 4.0, 0.5)
    min_vol_lots = st.number_input("最低成交張數", 100, 10000, 1500, 500)
    min_amount_yi = st.number_input("最低成交金額 (億元)", 0.1, 10.0, 1.0, 0.5)
    require_chip_bonus = st.checkbox("嚴格要求：近3日法人買超 且 融資未暴增", value=True)

st.info(f"📌 **當前濾網**：站上5/10/20/60MA、月季線翻揚、漲幅 **{min_chg}%~{max_chg}%**、上影線 < 實體1/3、當沖比 < 45%、週轉率 < 10%。")

if st.button("🚀 掃描台股全市場", use_container_width=True, type="primary"):
    with st.spinner("正在掃描台股上市櫃全市場，並交叉比對均線與法人融資數據..."):
        df_res, stats = run_screening(vol_mult, max_vol_mult, breakout_days, min_vol_lots, min_amount_yi, min_chg, max_chg, use_ma_tangle, max_tangle_pct, require_chip_bonus)
        st.session_state['scan_result'], st.session_state['scan_stats'] = df_res, stats

if 'scan_result' in st.session_state:
    df_res, stats = st.session_state['scan_result'], st.session_state.get('scan_stats', {})
    st.caption(f"📡 資料來源：{stats.get('source', '')} ｜ 總掃描：{stats.get('total', 0)} 檔 ｜ 初篩通過：{stats.get('stage1', 0)} 檔")
    if df_res.empty:
        st.warning("目前無同時滿足所有條件的標的！可點擊左上角 `>` 選單，試著取消「嚴格要求法人買超」或調降「最低漲幅」測試。")
    else:
        st.success(f"精選出 **{len(df_res)}** 檔符合條件的強勢突破股！")
        cols = ("代號", "名稱", "收盤價", "漲跌幅(%)", "成交張數", "5日量比", "當沖比(%)", "週轉率(%)", "3日法人(張)", "融資增減(張)")
        st.dataframe(df_res[list(cols)], use_container_width=True, hide_index=True)
        st.subheader("📊 個股技術線圖檢視")
        sel = st.selectbox("選擇要查看線圖的股票：", options=df_res["代號"] + " " + df_res["名稱"])
        row = df_res[df_res["代號"] == sel.split(" ").pop(0)].iloc[-1]
        hist = row["歷史資料"].tail(60)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['open'], high=hist['max'], low=hist['min'], close=hist['close'], name="K線", increasing_line_color='#ef5350', decreasing_line_color='#26a69a'))
        for m, c in ((5, 'orange'), (10, 'purple'), (20, 'blue'), (60, 'green')):
            fig.add_trace(go.Scatter(x=hist.index, y=hist[f'MA{m}'], line=dict(color=c, width=1.2), name=f'{m}MA'))
        fig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)
