import streamlit as st
import plotly.graph_objects as go
from screener import run_screening

st.set_page_config(page_title="台股波段動能選股雷達", page_icon="🎯", layout="centered")

st.title("🎯 台股波段動能選股雷達")
st.caption("防隔日沖濾網｜均線翻揚 × 溫和帶量 × 籌碼健康度")

with st.sidebar:
    st.header("⚙️ 專屬濾網參數微調")
    
    st.subheader("1. 均線與頸線突破")
    breakout_days = st.selectbox("突破關鍵頸線天數", options=(10, 20, 60), index=1)
    use_ma_tangle = st.checkbox("啟用均線糾結發散 (選配)", value=False)
    max_tangle_pct = st.slider("5/10/20日線最大乖離 (%)", min_value=2.0, max_value=8.0, value=5.0, step=0.5)
    
    st.subheader("2. 成交量與流動性")
    vol_mult = st.slider("5日均量最低倍數", min_value=1.0, max_value=3.0, value=1.5, step=0.1)
    max_vol_mult = st.slider("5日均量上限 (防爆天量)", min_value=2.5, max_value=6.0, value=4.0, step=0.5)
    min_vol_lots = st.number_input("最低成交張數", min_value=100, max_value=10000, value=1500, step=500)
    min_amount_yi = st.number_input("最低成交金額 (億元)", min_value=0.1, max_value=10.0, value=1.0, step=0.5)
    
    st.subheader("3. 籌碼加分項")
    require_chip_bonus = st.checkbox("嚴格要求：近3日法人買超 且 融資未暴增", value=True)

st.info("📌 **固定核心濾網**：站上5/10/20/60MA、月季線翻揚、漲幅 3.5%~8.5%（避開漲停）、上影線 < 實體1/3、當沖比 < 45%、週轉率 < 10%。")

if st.button("🚀 掃描台股全市場", use_container_width=True, type="primary"):
    with st.spinner("正在掃描台股上市櫃全市場，並交叉比對均線與法人融資數據（約需 15~30 秒）..."):
        df_res = run_screening(
            vol_mult=vol_mult,
            max_vol_mult=max_vol_mult,
            breakout_days=breakout_days,
            min_vol_lots=min_vol_lots,
            min_amount_yi=min_amount_yi,
            use_ma_tangle=use_ma_tangle,
            max_tangle_pct=max_tangle_pct,
            require_chip_bonus=require_chip_bonus
        )
        st.session_state['scan_result'] = df_res

if 'scan_result' in st.session_state:
    df_res = st.session_state['scan_result']
    if df_res.empty:
        st.warning("目前無完全符合條件的標的（若為週末假日部分資料源可能維護中，或可點左上角 `>` 放寬量比與法人條件測試）。")
    else:
        st.success(f"精選出 **{len(df_res)}** 檔符合「低隔日沖風險＋籌碼健康」的突破股！")
        
        display_cols = ("代號", "名稱", "收盤價", "漲跌幅(%)", "成交張數", "5日量比", "當沖比(%)", "週轉率(%)", "3日法人(張)", "融資增減(張)")
        st.dataframe(df_res[list(display_cols)], use_container_width=True, hide_index=True)
        
        st.subheader("📊 個股技術線圖檢視")
        selected_stock = st.selectbox(
            "選擇要查看線圖的股票：",
            options=df_res["代號"] + " " + df_res["名稱"]
        )
        stock_code = selected_stock.split(" ").pop(0)
        matched_df = df_res[df_res["代號"] == stock_code]
        row = matched_df.iloc[-1]
        hist = row["歷史資料"].tail(60)
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=hist.index, open=hist['open'], high=hist['max'],
            low=hist['min'], close=hist['close'], name="K線",
            increasing_line_color='#ef5350', decreasing_line_color='#26a69a'
        ))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA5'], line=dict(color='orange', width=1), name='5MA'))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA10'], line=dict(color='purple', width=1), name='10MA'))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA20'], line=dict(color='blue', width=1.5), name='20MA'))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA60'], line=dict(color='green', width=1.5), name='60MA'))
        
        fig.update_layout(
            height=400, margin=dict(l=10, r=10, t=30, b=10),
            xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig, use_container_width=True)
