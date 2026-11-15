import streamlit as st
import plotly.graph_objects as go
from screener import run_screening

st.set_page_config(page_title="台股波段動能選股雷達", page_icon="🎯", layout="centered")
st.title("🎯 台股波段動能選股雷達")
st.caption("全模組化獨立開關｜自由組合您的專屬選股濾網")

with st.sidebar:
    st.header("🎛️ 9 大濾網獨立開關")
    
    st.subheader("一、均線與趨勢結構")
    use_above_ma = st.checkbox("1. 站上所有均線 (5/10/20/60MA)", value=True)
    use_ma_up = st.checkbox("2. 中長期均線翻揚 (20/60MA向上)", value=True)
    use_tangle = st.checkbox("3. 均線糾結發散 (選配)", value=False)
    max_tangle = st.slider("　└ 5/10/20日線最大乖離 (%)", 2.0, 8.0, 5.0, 0.5) if use_tangle else 5.0

    st.subheader("二、價格型態與防隔日沖")
    use_brk = st.checkbox("4. 突破關鍵頸線 (創區間高)", value=True)
    brk_days = st.selectbox("　└ 突破天數門檻", options=(10, 20, 60), index=1) if use_brk else 20
    use_chg = st.checkbox("5. 漲幅區間與紅K限制", value=True)
    min_chg = st.slider("　└ 最低漲幅 (%)", 0.5, 8.0, 3.5, 0.5) if use_chg else 0.0
    max_chg = st.slider("　└ 最高漲幅 (% 含漲停)", 5.0, 10.5, 10.5, 0.5) if use_chg else 10.5
    use_shadow = st.checkbox("6. 拒收長上影線 (<實體1/3)", value=True)

    st.subheader("三、成交量與籌碼健康度")
    use_vol = st.checkbox("7. 溫和帶量攻擊 (防爆天量)", value=True)
    min_v5 = st.slider("　└ 5日均量最低倍數", 1.0, 3.0, 1.5, 0.1) if use_vol else 1.0
    max_v5 = st.slider("　└ 5日均量上限倍數", 2.5, 8.0, 4.0, 0.5) if use_vol else 8.0
    use_liq = st.checkbox("8. 流動性與當沖/週轉限制", value=True)
    min_lots = st.number_input("　└ 最低成交張數", 100, 10000, 1500, 500) if use_liq else 100
    min_yi = st.number_input("　└ 最低成交金額 (億元)", 0.1, 10.0, 1.0, 0.5) if use_liq else 0.1
    use_chip = st.checkbox("9. 法人買超 且 融資未暴增", value=True)

cfg = {
    "use_above_ma": use_above_ma, "use_ma_up": use_ma_up, "use_tangle": use_tangle, "max_tangle": max_tangle,
    "use_brk": use_brk, "brk_days": brk_days, "use_chg": use_chg, "min_chg": min_chg, "max_chg": max_chg,
    "use_shadow": use_shadow, "use_vol": use_vol, "min_v5": min_v5, "max_v5": max_v5,
    "use_liq": use_liq, "min_lots": min_lots, "min_yi": min_yi, "use_chip": use_chip
}

active_cnt = sum([use_above_ma, use_ma_up, use_tangle, use_brk, use_chg, use_shadow, use_vol, use_liq, use_chip])
st.info(f"🎛️ 目前已開啟 **{active_cnt} / 9** 項濾網條件（點擊左上角 `>` 可自由勾選或關閉任一條件）。")

if st.button("🚀 掃描台股全市場", use_container_width=True, type="primary"):
    with st.spinner("正在依您勾選的條件掃描台股..."):
        df_res, stats = run_screening(cfg)
        st.session_state['scan_result'], st.session_state['scan_stats'] = df_res, stats

if 'scan_result' in st.session_state:
    df_res, stats = st.session_state['scan_result'], st.session_state.get('scan_stats', {})
    st.caption(f"📡 資料來源：{stats.get('source', '')} ｜ 總掃描：{stats.get('total', 0)} 檔 ｜ 初篩通過：{stats.get('stage1', 0)} 檔")
    if df_res.empty:
        st.warning("目前無符合已勾選條件的標的！您可點擊左上角 `>` 取消部分勾選再按一次掃描。")
    else:
        st.success(f"精選出 **{len(df_res)}** 檔符合條件的強勢股！")
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
