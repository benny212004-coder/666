import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_all_tw_stocks_today():
    all_stocks = list()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r_twse = requests.get("https://twse.com.tw", headers=headers, timeout=15, verify=False)
        if r_twse.status_code == 200:
            for item in r_twse.json():
                code = str(item.get("Code", "")).strip()
                if len(code) == 4 and code.isdigit():
                    all_stocks.append({
                        "code": code,
                        "ticker": f"{code}.TW",
                        "name": str(item.get("Name", "")).strip(),
                        "open": item.get("OpeningPrice", ""),
                        "high": item.get("HighestPrice", ""),
                        "low": item.get("LowestPrice", ""),
                        "close": item.get("ClosingPrice", ""),
                        "change": item.get("Change", ""),
                        "volume": item.get("TradeVolume", ""),
                        "amount": item.get("TradeValue", "")
                    })
    except Exception:
        pass

    try:
        r_tpex = requests.get("https://tpex.org.tw", headers=headers, timeout=15, verify=False)
        if r_tpex.status_code == 200:
            for item in r_tpex.json():
                code = str(item.get("SecuritiesCompanyCode", "")).strip()
                if len(code) == 4 and code.isdigit():
                    all_stocks.append({
                        "code": code,
                        "ticker": f"{code}.TWO",
                        "name": str(item.get("CompanyName", "")).strip(),
                        "open": item.get("Open", ""),
                        "high": item.get("High", ""),
                        "low": item.get("Low", ""),
                        "close": item.get("Close", ""),
                        "change": item.get("Change", ""),
                        "volume": item.get("TradingShares", ""),
                        "amount": item.get("TransactionAmount", "")
                    })
    except Exception:
        pass
        
    return all_stocks

def fetch_single_chip_data(stock_id, start_date):
    base_url = "https://finmindtrade.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    inst_3d_net = 0
    margin_diff_lots = 0
    dt_shares = 0.0
    cap_stock = 0.0
    
    try:
        p_i = {"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}
        r_i = requests.get(base_url, params=p_i, headers=headers, timeout=8)
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
        p_m = {"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}
        r_m = requests.get(base_url, params=p_m, headers=headers, timeout=8)
        if r_m.status_code == 200 and r_m.text.strip():
            d_m = r_m.json().get("data")
            if d_m and len(d_m) >= 2:
                df_m = pd.DataFrame(d_m).sort_values("date").reset_index(drop=True)
                margin_diff_lots = int(df_m.iloc[-1]["MarginPurchaseTodayBalance"] - df_m.iloc[-2]["MarginPurchaseTodayBalance"])
    except Exception:
        pass

    try:
        p_dt = {"dataset": "TaiwanStockDayTrading", "data_id": stock_id, "start_date": start_date}
        r_dt = requests.get(base_url, params=p_dt, headers=headers, timeout=8)
        if r_dt.status_code == 200 and r_dt.text.strip():
            d_dt = r_dt.json().get("data")
            if d_dt:
                dt_shares = float(pd.DataFrame(d_dt).iloc[-1]["Volume"])
    except Exception:
        pass

    try:
        p_info = {"dataset": "TaiwanStockInfo", "data_id": stock_id}
        r_info = requests.get(base_url, params=p_info, headers=headers, timeout=8)
        if r_info.status_code == 200 and r_info.text.strip():
            d_info = r_info.json().get("data")
            if d_info:
                first_row = d_info[0] if isinstance(d_info, list) else d_info
                if isinstance(first_row, dict) and "capital_stock" in first_row:
                    cap_stock = float(first_row["capital_stock"])
    except Exception:
        pass
        
    return inst_3d_net, margin_diff_lots, dt_shares, cap_stock

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
    raw_market = fetch_all_tw_stocks_today()
    if not raw_market:
        return pd.DataFrame()
        
    candidates = list()
    invalid_vals = {"", "--", "---", "X", "None", "nan"}
    
    for item in raw_market:
        try:
            def to_f(v):
                s = str(v).replace(",", "").replace("+", "").strip()
                return float(s) if s not in invalid_vals else np.nan
                
            open_p = to_f(item["open"])
            high_p = to_f(item["high"])
            low_p = to_f(item["low"])
            close_p = to_f(item["close"])
            diff_p = to_f(item["change"])
            vol_shares = to_f(item["volume"])
            amount = to_f(item["amount"])
            
            if np.isnan((open_p, high_p, low_p, close_p, diff_p, vol_shares, amount)).any():
                continue
                
            vol_lots = vol_shares / 1000.0
            amount_yi = amount / 100000000.0
            if vol_lots < min_vol_lots or amount_yi < min_amount_yi:
                continue
                
            prev_close = close_p - diff_p
            if prev_close <= 0:
                continue
            change_pct = (diff_p / prev_close) * 100.0
            if not (3.5 <= change_pct <= 8.5):
                continue
            if close_p <= open_p:
                continue
                
            dist_to_high_pct = ((high_p - close_p) / close_p) * 100.0
            upper_shadow = high_p - close_p
            body_len = close_p - open_p
            if dist_to_high_pct >= 1.5 or upper_shadow >= (body_len / 3.0):
                continue
                
            candidates.append({
                "code": item["code"],
                "ticker": item["ticker"],
                "name": item["name"],
                "close": close_p,
                "change_pct": change_pct,
                "vol_lots": int(vol_lots),
                "vol_shares": vol_shares,
                "amount_yi": round(amount_yi, 2)
            })
        except Exception:
            continue

    if not candidates:
        return pd.DataFrame()

    cand_tickers = [c["ticker"] for c in candidates]
    raw_hist = yf.download(cand_tickers, period="5mo", group_by="ticker", progress=False, threads=True)
    
    start_date = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    final_results = list()
    
    for cand in candidates:
        ticker = cand["ticker"]
        code = cand["code"]
        try:
            df = raw_hist[ticker].dropna() if len(cand_tickers) > 1 else raw_hist.dropna()
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
            close_p = float(today["Close"])
            vol_shares = float(today["Volume"])
            
            if not (close_p > today["MA5"] and close_p > today["MA10"] and close_p > today["MA20"] and close_p > today["MA60"]):
                continue
                
            if not (today["MA20"] > yest["MA20"] and today["MA60"] >= yest["MA60"]):
                continue
                
            if use_ma_tangle:
                mas = (today["MA5"], today["MA10"], today["MA20"])
                tangle_pct = ((max(mas) - min(mas)) / min(mas)) * 100.0
                if tangle_pct > max_tangle_pct:
                    continue
                    
            prev_max_close = df["Close"].iloc[-(breakout_days+1):-1].max()
            if not (close_p > prev_max_close):
                continue
                
            prev_v5 = float(yest["Vol_MA5"])
            prev_v20 = float(yest["Vol_MA20"])
            if prev_v5 <= 0 or prev_v20 <= 0:
                continue
            v5_ratio = vol_shares / prev_v5
            v20_ratio = vol_shares / prev_v20
            if not (vol_mult < v5_ratio < max_vol_mult and v20_ratio > 1.5):
                continue
                
            inst_3d_net, margin_diff_lots, dt_shares, cap_stock = fetch_single_chip_data(code, start_date)
            
            dt_ratio = (dt_shares / cand["vol_shares"]) * 100.0 if (cand["vol_shares"] > 0 and dt_shares > 0) else 0.0
            if dt_ratio >= 45.0:
                continue
                
            turnover_pct = 0.0
            if cap_stock > 0:
                total_shares = cap_stock / 10.0
                turnover_pct = (cand["vol_shares"] / total_shares) * 100.0
                if turnover_pct >= 10.0:
                    continue
                    margin_ok = margin_diff_lots < (cand["vol_lots"] * 0.15)
if require_chip_bonus:
if inst_3d_net <= 0 or not margin_ok:
continue
df_chart = df.rename(columns={"Open": "open", "High": "max", "Low": "min", "Close": "close"})
final_results.append({
"代號": code,
"名稱": cand["name"],
"收盤價": round(cand["close"], 2),
"漲跌幅(%)": round(cand["change_pct"], 2),
"成交張數": cand["vol_lots"],
"金額(億)": cand["amount_yi"],
"5日量比": round(v5_ratio, 2),
"當沖比(%)": round(dt_ratio, 1),
"週轉率(%)": round(turnover_pct, 2),
"3日法人(張)": inst_3d_net,
"融資增減(張)": margin_diff_lots,
"歷史資料": df_chart
})
time.sleep(0.1)
except Exception:
continue
res_df = pd.DataFrame(final_results)
if not res_df.empty:
res_df = res_df.sort_values(by="3日法人(張)", ascending=False).reset_index(drop=True)
return res_df
