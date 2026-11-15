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
    return dt.strftime("%Y%m%d"), dt.strftime("%Y-%m-%d")

def fetch_twse_daily_all(date_str):
    url = f"https://twse.com.tw{date_str}&type=ALLBUT0999"
    res = requests.get(url, timeout=15).json()
    if res.get("stat") != "OK":
        return pd.DataFrame()
    
    target_table = None
    for table in res.get("tables", []):
        if "證券代號" in table.get("fields", []) and "收盤價" in table.get("fields", []):
            target_table = table
            break
    if not target_table:
        return pd.DataFrame()
        
    df = pd.DataFrame(target_table["data"], columns=target_table["fields"])
    df = df[df["證券代號"].str.len() == 4].copy()
    return df

def fetch_day_trade_ratio(date_str):
    url = f"https://twse.com.tw{date_str}"
    try:
        res = requests.get(url, timeout=15).json()
        if res.get("stat") != "OK":
            return {}
        df = pd.DataFrame(res["data"], columns=res["fields"])
        dt_dict = {}
        for _, r in df.iterrows():
            code = str(r["證券代號"]).strip()
            vol_str = str(r["當日沖銷交易成交股數"]).replace(",", "")
            if vol_str.isdigit():
                dt_dict[code] = int(vol_str)
        return dt_dict
    except Exception:
        return {}

def fetch_finmind_chip_and_hist(stock_id, start_date):
    base_url = "https://finmindtrade.com"
    
    p_price = {"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date}
    r_price = requests.get(base_url, params=p_price, timeout=10).json()
    df_p = pd.DataFrame(r_price.get("data", []))
    
    p_inst = {"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}
    r_inst = requests.get(base_url, params=p_inst, timeout=10).json()
    df_i = pd.DataFrame(r_inst.get("data", []))
    
    p_margin = {"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}
    r_margin = requests.get(base_url, params=p_margin, timeout=10).json()
    df_m = pd.DataFrame(r_margin.get("data", []))
    
    p_info = {"dataset": "TaiwanStockInfo", "data_id": stock_id}
    r_info = requests.get(base_url, params=p_info, timeout=10).json()
    df_info = pd.DataFrame(r_info.get("data", []))
    
    return df_p, df_i, df_m, df_info

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
    date_str, dash_date = get_latest_trading_date()
    
    daily_df = fetch_twse_daily_all(date_str)
    if daily_df.empty:
        prev_dt = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=1)
        while prev_dt.weekday() >= 5:
            prev_dt -= timedelta(days=1)
        date_str = prev_dt.strftime("%Y%m%d")
        dash_date = prev_dt.strftime("%Y-%m-%d")
        daily_df = fetch_twse_daily_all(date_str)
        
    start_date = (datetime.strptime(dash_date, "%Y-%m-%d") - timedelta(days=110)).strftime("%Y-%m-%d")
    dt_vol_map = fetch_day_trade_ratio(date_str)
    candidates = []
    
    for _, row in daily_df.iterrows():
        try:
            code = str(row["證券代號"]).strip()
            name = str(row["證券名稱"]).strip()
            
            def to_f(val):
                s = str(val).replace(",", "").strip()
                return float(s) if s not in ["", "--", "X"] else np.nan
                
            open_p = to_f(row["開盤價"])
            high_p = to_f(row["最高價"])
            low_p = to_f(row["最低價"])
            close_p = to_f(row["收盤價"])
            vol_shares = to_f(row["成交股數"])
            amount = to_f(row["成交金額"])
            diff_sign = str(row["漲跌(+/-)"]).strip()
            diff_val = to_f(row["漲跌價差"])
            
            if np.isnan([open_p, high_p, low_p, close_p, vol_shares, amount]).any():
                continue
                
            vol_lots = vol_shares / 1000.0
            amount_yi = amount / 100000000.0
            if vol_lots < min_vol_lots or amount_yi < min_amount_yi:
                continue
                
            signed_diff = diff_val if "+" in diff_sign else (-diff_val if "-" in diff_sign else 0.0)
            prev_close = close_p - signed_diff
            if prev_close <= 0:
                continue
            change_pct = (signed_diff / prev_close) * 100.0
            
            if not (3.5 <= change_pct <= 8.5):
                continue
            if close_p <= open_p:
                continue
                
            dist_to_high_pct = ((high_p - close_p) / close_p) * 100.0
            upper_shadow = high_p - close_p
            body_len = close_p - open_p
            if dist_to_high_pct >= 1.5 or upper_shadow >= (body_len / 3.0):
                continue
                
            dt_shares = dt_vol_map.get(code, 0)
            dt_ratio = (dt_shares / vol_shares) * 100.0 if vol_shares > 0 else 0.0
            if dt_ratio >= 45.0:
                continue
                
            candidates.append({
                "code": code,
                "name": name,
                "close": close_p,
                "change_pct": change_pct,
                "vol_lots": int(vol_lots),
                "amount_yi": round(amount_yi, 2),
                "dt_ratio": round(dt_ratio, 1)
            })
        except Exception:
            continue

    final_results = []
    for cand in candidates:
        code = cand["code"]
        try:
            df_p, df_i, df_m, df_info = fetch_finmind_chip_and_hist(code, start_date)
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
                mas = [today["MA5"], today["MA10"], today["MA20"]]
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
                
            turnover_pct = 0.0
            if not df_info.empty and "capital_stock" in df_info.columns:
                cap = float(df_info.iloc["capital_stock"])
                total_shares = cap / 10.0
                if total_shares > 0:
                    turnover_pct = (today["Trading_Volume"] / total_shares) * 100.0
                    if turnover_pct >= 10.0:
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
                "週轉率(%)": round(turnover_pct, 2),
                "3日法人(張)": inst_3d_net,
                "融資增減(張)": margin_diff_lots,
                "歷史資料": df_p
            })
            time.sleep(0.2)
        except Exception:
            continue
            
    res_df = pd.DataFrame(final_results)
    if not res_df.empty:
        res_df = res_df.sort_values(by="3日法人(張)", ascending=False).reset_index(drop=True)
    return res_df
