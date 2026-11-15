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
    url = "https://finmindtrade.com"
    params = {
        "dataset": "TaiwanStockPrice",
        "start_date": target_date,
        "end_date": target_date
    }
    res = requests.get(url, params=params, timeout=20).json()
    data = res.get("data")
    return pd.DataFrame(data) if data else pd.DataFrame()

def fetch_finmind_day_trade(target_date):
    url = "https://finmindtrade.com"
    params = {
        "dataset": "TaiwanStockDayTrading",
        "start_date": target_date,
        "end_date": target_date
    }
    try:
        res = requests.get(url, params=params, timeout=20).json()
        data = res.get("data")
        df = pd.DataFrame(data) if data else pd.DataFrame()
        if df.empty:
            return {}
        return dict(zip(df["stock_id"], df["Volume"]))
    except Exception:
        return {}

def fetch_stock_names():
    url = "https://finmindtrade.com"
    params = {"dataset": "TaiwanStockInfo"}
    try:
        res = requests.get(url, params=params, timeout=20).json()
        data = res.get("data")
        df = pd.DataFrame(data) if data else pd.DataFrame()
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
    base_url = "https://finmindtrade.com"
    
    r_p = requests.get(base_url, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date}, timeout=12).json()
    d_p = r_p.get("data")
    df_p = pd.DataFrame(d_p) if d_p else pd.DataFrame()
    
    r_i = requests.get(base_url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, timeout=12).json()
    d_i = r_i.get("data")
    df_i = pd.DataFrame(d_i) if d_i else pd.DataFrame()
    
    r_m = requests.get(base_url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, timeout=12).json()
    d_m = r_m.get("data")
    df_m = pd.DataFrame(d_m) if d_m else pd.DataFrame()
    
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
            
            vol_lots = vol_shares / 1000.0
            amount_yi = amount / 100000000.0
            if vol_lots < min_vol_lots or amount_yi < min_amount_yi:
                continue
                
            prev_close = close_p - spread
            if prev_close <= 0:
                continue
            change_pct = (spread / prev_close) * 100.0
            
            if not (3.5 <= change_pct <= 8.5):
                continue
            if close_p <= open_p:
                continue
                
            dist_to_high_pct = ((high_p - close_p) / close_p) * 100.0
            upper_shadow = high_p - close_p
            body_len = close_p - open_p
            if dist_to_high_pct >= 1.5 or upper_shadow >= (body_len / 3.0):
                continue
                
            dt_shares = float(dt_vol_map.get(code, 0))
            dt_ratio = (dt_shares / vol_shares) * 100.0 if vol_shares > 0 else 0.0
            if dt_ratio >= 45.0:
                continue
                
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
            
            c = today["close"]
            if not (c > today["MA5"] and c > today["MA10"] and c > today["MA20"] and c > today["MA60"]):
                continue
                
            if not (today["MA20"] > yest["MA20"] and today["MA60"] >= yest["MA60"]):
                continue
                
            if use_ma_tangle:
                mas = list((today["MA5"], today["MA10"], today["MA20"]))
                tangle_pct = ((max(mas) - min(mas)) / min(mas)) * 100.0
                if tangle_pct > max_tangle_pct:
                    continue
                    
            prev_max_close = df_p["close"].iloc[-(breakout_days+1):-1].max()
            if not (c > prev_max_close):
                continue
                
            prev_v5 = yest["Vol_MA5"]
            prev_v20 = yest["Vol_MA20"]
            if prev_v5 <= 0 or prev_v20 <= 0:
                continue
            v5_ratio = today["Trading_Volume"] / prev_v5
            v20_ratio = today["Trading_Volume"] / prev_v20
            if not (vol_mult < v5_ratio < max_vol_mult and v20_ratio > 1.5):
                continue
                
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
            continue
            
    res_df = pd.DataFrame(final_results)
    if not res_df.empty:
        res_df = res_df.sort_values(by="3日法人(張)", ascending=False).reset_index(drop=True)
    return res_df
