import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

def get_latest_trading_date():
    dt = datetime.now()
    if dt.hour < 15 or (dt.hour == 15 and dt.minute < 30):
        dt -= timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y-%m-%d")

def fetch_finmind_market_daily(target_date):
    """透過 FinMind 取得台股全市場（上市+上櫃）單日行情"""
    url = "https://finmindtrade.com"
    params = {
        "dataset": "TaiwanStockPrice",
        "start_date": target_date,
        "end_date": target_date
    }
    res = requests.get(url, params=params, timeout=20).json()
    return pd.DataFrame(res.get("data", []))

def fetch_finmind_day_trade(target_date):
    """透過 FinMind 取得台股全市場當日沖銷數據"""
    url = "https://finmindtrade.com"
    params = {
        "dataset": "TaiwanStockDayTrading",
        "start_date": target_date,
        "end_date": target_date
    }
    try:
        res = requests.get(url, params=params, timeout=20).json()
        df = pd.DataFrame(res.get("data", []))
        if df.empty:
            return {}
        return dict(zip(df["stock_id"], df["Volume"]))
    except Exception:
        return {}

def fetch_stock_names():
    """取得台股上市櫃代號與中文名稱對照表"""
    url = "https://finmindtrade.com"
    params = {"dataset": "TaiwanStockInfo"}
    try:
        res = requests.get(url, params=params, timeout=20).json()
        df = pd.DataFrame(res.get("data", []))
        if df.empty:
            return {}, {}
        df = df.drop_duplicates(subset=["stock_id"])
        name_map = dict(zip(df["stock_id"], df["stock_name"]))
        cap_map = {}
        if "capital_stock" in df.columns:
            cap_map = dict(zip(df["stock_id"], df["capital_stock"]))
        return name_map, cap_map
    except Exception:
        return {}, {}

def fetch_single_stock_detail(stock_id, start_date):
    """針對通過初篩的候選股，取得近 4 個月日K、三大法人、融資券"""
    base_url = "https://finmindtrade.com"
    
    r_p = requests.get(base_url, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date}, timeout=12).json()
    df_p = pd.DataFrame(r_p.get("data", []))
    
    r_i = requests.get(base_url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, timeout=12).json()
    df_i = pd.DataFrame(r_i.get("data", []))
    
    r_m = requests.get(base_url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, timeout=12).json()
    df_m = pd.DataFrame(r_m.get("data", []))
    
    return df_p, df_i, df_m

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
    dash_date = get_latest_trading_date()
    daily_df = fetch_finmind_market_daily(dash_date)
    
    # 若遇國定假日或尚未開盤，自動往回尋找最近一個有資料的交易日 (最多回推 7 天)
    for _ in range(7):
        if not daily_df.empty:
            break
        prev_dt = datetime.strptime(dash_date, "%Y-%m-%d") - timedelta(days=1)
        while prev_dt.weekday() >= 5:
            prev_dt -= timedelta(days=1)
        dash_date = prev_dt.strftime("%Y-%m-%d")
        daily_df = fetch_finmind_market_daily(dash_date)
        
    if daily_df.empty:
        return pd.DataFrame()
        
    start_date = (datetime.strptime(dash_date, "%Y-%m-%d") - timedelta(days=115)).strftime("%Y-%m-%d")
    dt_vol_map = fetch_finmind_day_trade(dash_date)
    name_map, cap_map = fetch_stock_names()
    
    # 第一階段：全市場初篩（過濾普通股 4 碼代號、流動性、漲幅 3.5%~8.5%、拒收長上影線、當沖比 < 45%）
    daily_df = daily_df[daily_df["stock_id"].str.len() == 4].copy()
    candidates = []
    
    for _, row in daily_df.iterrows():
        try:
            code = str(row["stock_id"]).strip()
            open_p = float(row["open"])
            high_p = float(row["max"])
            low_p = float(row["min"])
            close_p = float(row["close"])
            vol_shares = float(row["Trading_Volume"])
            amount = float(row["Trading_money"])
            spread = float(row["spread"])
            
            # 流動性門檻：成交張數 > 1500 張 且 成交金額 > 1 億元
            vol_lots = vol_shares / 1000.0
            amount_yi = amount / 100000000.0
            if vol_lots < min_vol_lots or amount_yi < min_amount_yi:
                continue
                
            prev_close = close_p - spread
            if prev_close <= 0:
                continue
            change_pct = (spread / prev_close) * 100.0
            
            # 二、溫和強勢紅K：漲幅介於 3.5% ~ 8.5%（嚴格排除 >= 9.5% 漲停）
            if not (3.5 <= change_pct <= 8.5):
                continue
            if close_p <= open_p:
                continue
                
            # 二、拒收長上影線：收盤距最高 < 1.5% 且 上影線 < 實體紅K的 1/3
            dist_to_high_pct = ((high_p - close_p) / close_p) * 100.0
            upper_shadow = high_p - close_p
            body_len = close_p - open_p
            if dist_to_high_pct >= 1.5 or upper_shadow >= (body_len / 3.0):
                continue
                
            # 三、當沖比率 < 45%
            dt_shares = float(dt_vol_map.get(code, 0))
            dt_ratio = (dt_shares / vol_shares) * 100.0 if vol_shares > 0 else 0.0
            if dt_ratio >= 45.0:
                continue
                
            # 三、週轉率 < 10%
            turnover_pct = 0.0
            cap = float(cap_map.get(code, 0))
            if cap > 0:
                total_shares = cap / 10.0
                turnover_pct = (vol_shares / total_shares) * 100.0
                if turnover_pct >= 10.0:
                    continue
                    
            candidates.append({
                "code": code,
                "name": name_map.get(code, code),
                "close": close_p,
                "change_pct": change_pct,
                "vol_lots": int(vol_lots),
                "amount_yi": round(amount_yi, 2),
                "dt_ratio": round(dt_ratio, 1),
                "turnover_pct": round(turnover_pct, 2)
            })
        except Exception:
            continue

    # 第二階段：精準驗證均線翻揚、突破頸線、5日/20日量比、法人與融資結構
    final_results = []
    for cand in candidates:
        code = cand["code"]
        try:
            df_p, df_i, df_m = fetch_single_stock_detail(code, start_date)
            if len(df_p) < 62:
                continue
                
            df_p = df_p.sort_values("date").reset_index(drop=True)
            df_p["MA5"] = df_p["close"].rolling(5).mean()
            df_p["MA10"] = df_p["close"].rolling(10).mean()
            df_p["MA20"] = df_p["close"].rolling(20).mean()
            df_p["MA60"] = df_p["close"].rolling(60).mean()
            df_p["Vol_MA5"] = df_p["Trading_Volume"].rolling(5).mean()
            df_p["Vol_MA20"] = df_p["Trading_Volume"].rolling(20).mean()
            
            today = df_p.iloc[-1]
            yest = df_p.iloc[-2]
            
            # 一、站上所有均線 (收盤 > 5, 10, 20, 60MA)
            c = today["close"]
            if not (c > today["MA5"] and c > today["MA10"] and c > today["MA20"] and c > today["MA60"]):
                continue
                
            # 一、中長期均線翻揚 (今日20MA > 昨日20MA 且 今日60MA >= 昨日60MA)
            if not (today["MA20"] > yest["MA20"] and today["MA60"] >= yest["MA60"]):
                continue
                
            # 一、均線糾結發散 (選配)
            if use_ma_tangle:
                mas = [today["MA5"], today["MA10"], today["MA20"]]
                tangle_pct = ((max(mas) - min(mas)) / min(mas)) * 100.0
                if tangle_pct > max_tangle_pct:
                    continue
                    
            # 二、突破關鍵頸線：今日收盤 > 近 N 日最高收盤價
            prev_max_close = df_p["close"].iloc[-(breakout_days+1):-1].max()
            if not (c > prev_max_close):
                continue
                
            # 三、溫和帶量攻擊：1.5倍 < 今日量/5日均量 < 4倍，且 今日量 > 20日均量 1.5倍
            prev_v5 = yest["Vol_MA5"]
            prev_v20 = yest["Vol_MA20"]
            if prev_v5 <= 0 or prev_v20 <= 0:
                continue
            v5_ratio = today["Trading_Volume"] / prev_v5
            v20_ratio = today["Trading_Volume"] / prev_v20
            if not (vol_mult < v5_ratio < max_vol_mult and v20_ratio > 1.5):
                continue
                
            # 三、法人與資券結構
            inst_3d_net = 0
            if not df_i.empty:
                df_i_recent = df_i[df_i["date"].isin(df_p["date"].tail(3))]
                inst_3d_net = int((df_i_recent["buy"].sum() - df_i_recent["sell"].sum()) / 1000)
                
            margin_ok = True
            margin_diff_lots = 0
            if len(df_m) >= 2:
                df_m = df_m.sort_values("date").reset_index(drop=True)
                m_today = df_m.iloc[-1]["MarginPurchaseTodayBalance"]
                m_yest = df_m.iloc[-2]["MarginPurchaseTodayBalance"]
                margin_diff_lots = int(m_today - m_yest)
                if margin_diff_lots >= (cand["vol_lots"] * 0.15):
                    margin_ok = False
                    
            if require_chip_bonus:
                if inst_3d_net <= 0 or not margin_ok:
                    continue
                    
            df_p["date"] = pd.to_datetime(df_p["date"])
            df_p = df_p.set_index("date")
            
            final_results.append({
                "代號": code,
                "名稱": cand["name"],
                "收盤價": cand["close"],
                "漲跌幅(%)": round(cand["change_pct"], 2),
                "成交張數": cand["vol_lots"],
                "金額(億)": cand["amount_yi"],
                "5日量比": round(v5_ratio, 2),
                "當沖比(%)": cand["dt_ratio"],
                "週轉率(%)": cand["turnover_pct"],
                "3日法人(張)": inst_3d_net,
                "融資增減(張)": margin_diff_lots,
                "歷史資料": df_p
            })
            time.sleep(0.15)
        except Exception:
