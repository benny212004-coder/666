import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# 涵蓋台股上市櫃主流、權值、AI、重電、航運、生技、金融、傳產與高周轉熱門股
TW_UNIVERSE = {
    "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "2382.TW": "廣達",
    "2308.TW": "台達電", "2881.TW": "富邦金", "2882.TW": "國泰金", "2891.TW": "中信金",
    "2303.TW": "聯電", "3711.TW": "日月光投控", "3231.TW": "緯創", "2357.TW": "華碩",
    "3017.TW": "奇鋐", "3324.TWO": "雙鴻", "2376.TW": "技嘉", "6669.TW": "緯穎",
    "2603.TW": "長榮", "2609.TW": "陽明", "2615.TW": "萬海", "2618.TW": "長榮航",
    "2610.TW": "華航", "2379.TW": "瑞昱", "3034.TW": "聯詠", "3008.TW": "大立光",
    "2327.TW": "國巨", "2345.TW": "智邦", "3661.TW": "世芯-KY", "3443.TW": "創意",
    "3533.TW": "嘉澤", "1513.TW": "中興電", "1519.TW": "華城", "1503.TW": "士電",
    "1504.TW": "東元", "2002.TW": "中鋼", "1605.TW": "華新", "2353.TW": "宏碁",
    "2324.TW": "仁寶", "4938.TW": "和碩", "2301.TW": "光寶科", "2356.TW": "英業達",
    "2409.TW": "友達", "3481.TW": "群創", "2344.TW": "華邦電", "2408.TW": "南亞科",
    "8299.TWO": "群聯", "3260.TWO": "威剛", "6239.TW": "力成", "2449.TW": "京元電子",
    "3037.TW": "欣興", "3189.TW": "景碩", "8046.TW": "南電", "2313.TW": "華通",
    "2368.TW": "金像電", "6274.TWO": "台燿", "2383.TW": "台光電", "3044.TW": "健鼎",
    "5483.TWO": "中美晶", "6488.TWO": "環球晶", "3105.TWO": "穩懋", "8069.TWO": "元太",
    "5347.TWO": "世界", "3293.TWO": "鈊象", "6510.TWO": "精測", "5274.TWO": "信驊",
    "2474.TW": "可成", "2354.TW": "鴻準", "3005.TW": "神基", "3706.TW": "神達",
    "2377.TW": "微星", "2421.TW": "建準", "3653.TW": "健策", "6285.TW": "啟碁",
    "5388.TW": "中磊", "3596.TW": "智易", "4968.TW": "立積", "2458.TW": "義隆",
    "3035.TW": "智原", "6531.TW": "愛普*", "2337.TW": "旺宏", "3006.TW": "晶豪科",
    "4919.TW": "新唐", "6770.TW": "力積電", "5340.TWO": "建榮", "1815.TWO": "富喬",
    "8358.TWO": "金居", "6182.TWO": "合晶", "3532.TW": "台勝科", "3707.TWO": "漢磊",
    "3016.TWO": "嘉晶", "2360.TW": "致茂", "6196.TW": "帆宣", "3413.TW": "京鼎",
    "3583.TW": "辛耘", "3131.TWO": "弘塑", "6640.TWO": "均華", "5443.TWO": "均豪",
    "2464.TW": "盟立", "2049.TW": "上銀", "1590.TW": "亞德客-KY", "4576.TW": "大銀微系統",
    "2201.TW": "裕隆", "2204.TW": "中華", "1319.TW": "東陽", "1522.TW": "堤維西",
    "2634.TW": "漢翔", "8033.TW": "雷虎", "2630.TW": "亞航", "5284.TW": "jpp-KY",
    "6446.TW": "藥華藥", "6472.TW": "保瑞", "1795.TW": "美時", "4743.TWO": "合一",
    "9958.TW": "世紀鋼", "3708.TW": "上緯投控", "6806.TW": "森崴能源", "1609.TW": "大亞",
    "1608.TW": "華榮", "2501.TW": "國建", "2542.TW": "興富發", "5522.TW": "遠雄"
}

def fetch_single_chip_data(stock_id, start_date):
    """針對通過技術面篩選的強勢股，單獨查詢三大法人、融資、當沖與股本"""
    base_url = "https://finmindtrade.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    inst_3d_net = 0
    margin_diff_lots = 0
    margin_ok = True
    dt_ratio = 0.0
    turnover_pct = 0.0
    
    try:
        r_i = requests.get(base_url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, headers=headers, timeout=8)
        if r_i.status_code == 200 and r_i.text.strip():
            d_i = r_i.json().get("data")
            if d_i:
                df_i = pd.DataFrame(d_i)
                recent_dates = sorted(df_i["date"].unique())[-3:]
                df_i_recent = df_i[df_i["date"].isin(recent_dates)]
                inst_3d_net = int((df_i_recent["buy"].sum() - df_i_recent["sell"].sum()) / 1000)
    except Exception:
        pass

    try:
        r_m = requests.get(base_url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, headers=headers, timeout=8)
        if r_m.status_code == 200 and r_m.text.strip():
            d_m = r_m.json().get("data")
            if d_m and len(d_m) >= 2:
                df_m = pd.DataFrame(d_m).sort_values("date").reset_index(drop=True)
                margin_diff_lots = int(df_m.iloc[-1]["MarginPurchaseTodayBalance"] - df_m.iloc[-2]["MarginPurchaseTodayBalance"])
    except Exception:
        pass

    try:
        r_dt = requests.get(base_url, params={"dataset": "TaiwanStockDayTrading", "data_id": stock_id, "start_date": start_date}, headers=headers, timeout=8)
        if r_dt.status_code == 200 and r_dt.text.strip():
            d_dt = r_dt.json().get("data")
            if d_dt:
                dt_shares = float(pd.DataFrame(d_dt).iloc[-1]["Volume"])
                return inst_3d_net, margin_diff_lots, dt_shares
    except Exception:
        pass
        
    return inst_3d_net, margin_diff_lots, 0.0

def run_screening(
    vol_mult=1.5,
    max_vol_mult=4.0,
    breakout_days=20,
    min_vol_lots=1500,
    min_amount_yi=1.0,
    use_ma_tangle=False,
    max_tangle_pct=5.0,
    require_chip_bonus=True
):
    tickers = list(TW_UNIVERSE.keys())
    raw_data = yf.download(tickers, period="5mo", group_by="ticker", progress=False, threads=True)
    
    if raw_data.empty:
        return pd.DataFrame()
        
    start_date = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    final_results = []
    
    for ticker in tickers:
        try:
            df = raw_data[ticker].dropna()
            if len(df) < 62:
                continue
                
            df = df.copy()
            df["MA5"] = df["Close"].rolling(5).mean()
            df["MA10"] = df["Close"].rolling(10).mean()
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA60"] = df["Close"].rolling(60).mean()
            df["Vol_MA5"] = df["Volume"].rolling(5).mean()
            df["Vol_MA20"] = df["Volume"].rolling(20).mean()
            
            today = df.iloc[-1]
            yest = df.iloc[-2]
            
            open_p = float(today["Open"])
            high_p = float(today["High"])
            low_p = float(today["Low"])
            close_p = float(today["Close"])
            prev_close = float(yest["Close"])
            vol_shares = float(today["Volume"])
            
            # 流動性門檻：成交張數 > 1500 張 且 成交金額 > 1 億元
            vol_lots = vol_shares / 1000.0
            amount_yi = (close_p * vol_shares) / 100000000.0
            if vol_lots < min_vol_lots or amount_yi < min_amount_yi:
                continue
                
            # 漲跌幅與紅K確認：3.5% ~ 8.5% (嚴格排除 >= 9.5% 漲停)
            if prev_close <= 0:
                continue
            change_pct = ((close_p - prev_close) / prev_close) * 100.0
            if not (3.5 <= change_pct <= 8.5):
                continue
            if close_p <= open_p:
                continue
                
            # 拒收長上影線：收盤距最高 < 1.5% 且 上影線 < 實體紅K的 1/3
            dist_to_high_pct = ((high_p - close_p) / close_p) * 100.0
            upper_shadow = high_p - close_p
            body_len = close_p - open_p
            if dist_to_high_pct >= 1.5 or upper_shadow >= (body_len / 3.0):
                continue
                
            # 站上所有均線 (收盤 > 5, 10, 20, 60MA)
            if not (close_p > today["MA5"] and close_p > today["MA10"] and close_p > today["MA20"] and close_p > today["MA60"]):
                continue
                
            # 中長期均線翻揚 (今日20MA > 昨日20MA 且 今日60MA >= 昨日60MA)
            if not (today["MA20"] > yest["MA20"] and today["MA60"] >= yest["MA60"]):
                continue
                
            # 均線糾結發散 (選配)
            if use_ma_tangle:
                mas = list((today["MA5"], today["MA10"], today["MA20"]))
                tangle_pct = ((max(mas) - min(mas)) / min(mas)) * 100.0
                if tangle_pct > max_tangle_pct:
                    continue
                    
            # 突破關鍵頸線：今日收盤 > 近 N 日最高收盤價
            prev_max_close = df["Close"].iloc[-(breakout_days+1):-1].max()
            if not (close_p > prev_max_close):
                continue
                
            # 溫和帶量攻擊：1.5倍 < 今日量/5日均量 < 4倍，且 今日量 > 20日均量 1.5倍
            prev_v5 = float(yest["Vol_MA5"])
            prev_v20 = float(yest["Vol_MA20"])
            if prev_v5 <= 0 or prev_v20 <= 0:
                continue
            v5_ratio = vol_shares / prev_v5
            v20_ratio = vol_shares / prev_v20
            if not (vol_mult < v5_ratio < max_vol_mult and v20_ratio > 1.5):
                continue
                
            # 針對通過技術面篩選的股票，查詢籌碼與當沖數據
            code = ticker.replace(".TW", "").replace(".TWO", "")
            inst_3d_net, margin_diff_lots, dt_shares = fetch_single_chip_data(code, start_date)
            
            dt_ratio = (dt_shares / vol_shares) * 100.0 if (vol_shares > 0 and dt_shares > 0) else 0.0
            if dt_ratio >= 45.0:
                continue
                
            margin_ok = margin_diff_lots < (vol_lots * 0.15)
            if require_chip_bonus:
                if inst_3d_net <= 0 or not margin_ok:
                    continue
                    
            # 統一欄位名稱以配合 K 線圖繪製
            df_chart = df.rename(columns={"Open": "open", "High": "max", "Low": "min", "Close": "close"})
            
            final_results.append({
                "代號": code,
                "名稱": TW_UNIVERSE[ticker],
                "收盤價": round(close_p, 2),
                "漲跌幅(%)": round(change_pct, 2),
                "成交張數": int(vol_lots),
                "金額(億)": round(amount_yi, 2),
                "5日量比": round(v5_ratio, 2),
                "當沖比(%)": round(dt_ratio, 1),
                "週轉率(%)": "-",
                "3日法人(張)": inst_3d_net,
                "融資增減(張)": margin_diff_lots,
                "歷史資料": df_chart
            })
            time.sleep(0.1)
        except Exception:
            continue
            
    res_df = pd.DataFrame(final_results)
    if not res_df.empty:
        res_df = res_df.sort_values(by="5日量比", ascending=False).reset_index(drop=True)
    return res_df
