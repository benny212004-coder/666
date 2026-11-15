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
        r1 = requests.get("https://twse.com.tw", headers=headers, timeout=15, verify=False)
        if r1.status_code == 200:
            for it in r1.json():
                c = str(it.get("Code", "")).strip()
                if len(c) == 4 and c.isdigit():
                    all_stocks.append({"code": c, "ticker": f"{c}.TW", "name": str(it.get("Name", "")).strip(), "open": it.get("OpeningPrice", ""), "high": it.get("HighestPrice", ""), "low": it.get("LowestPrice", ""), "close": it.get("ClosingPrice", ""), "change": it.get("Change", ""), "volume": it.get("TradeVolume", ""), "amount": it.get("TradeValue", "")})
    except Exception:
        pass
    try:
        r2 = requests.get("https://tpex.org.tw", headers=headers, timeout=15, verify=False)
        if r2.status_code == 200:
            for it in r2.json():
                c = str(it.get("SecuritiesCompanyCode", "")).strip()
                if len(c) == 4 and c.isdigit():
                    all_stocks.append({"code": c, "ticker": f"{c}.TWO", "name": str(it.get("CompanyName", "")).strip(), "open": it.get("Open", ""), "high": it.get("High", ""), "low": it.get("Low", ""), "close": it.get("Close", ""), "change": it.get("Change", ""), "volume": it.get("TradingShares", ""), "amount": it.get("TransactionAmount", "")})
    except Exception:
        pass
    return all_stocks

def fetch_single_chip_data(stock_id, start_date):
    url = "https://finmindtrade.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    inst_net, margin_diff, dt_shares, cap_stock = 0, 0, 0.0, 0.0
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, headers=headers, timeout=8)
        if r.status_code == 200 and r.text.strip():
            d = r.json().get("data")
            if d:
                df = pd.DataFrame(d)
                df_r = df[df["date"].isin(sorted(df["date"].unique())[-3:])]
                inst_net = int((df_r["buy"].sum() - df_r["sell"].sum()) / 1000)
    except Exception:
        pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, headers=headers, timeout=8)
        if r.status_code == 200 and r.text.strip():
            d = r.json().get("data")
            if d and len(d) >= 2:
                df = pd.DataFrame(d).sort_values("date").reset_index(drop=True)
                margin_diff = int(df.iloc[-1]["MarginPurchaseTodayBalance"] - df.iloc[-2]["MarginPurchaseTodayBalance"])
    except Exception:
        pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockDayTrading", "data_id": stock_id, "start_date": start_date}, headers=headers, timeout=8)
        if r.status_code == 200 and r.text.strip():
            d = r.json().get("data")
            if d:
                dt_shares = float(pd.DataFrame(d).iloc[-1]["Volume"])
    except Exception:
        pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInfo", "data_id": stock_id}, headers=headers, timeout=8)
        if r.status_code == 200 and r.text.strip():
            d = r.json().get("data")
            if d:
                row0 = next(iter(d)) if isinstance(d, list) else d
                if isinstance(row0, dict) and "capital_stock" in row0:
                    cap_stock = float(row0["capital_stock"])
    except Exception:
        pass
    return inst_net, margin_diff, dt_shares, cap_stock

def run_screening(vol_mult=1.5, max_vol_mult=4.0, breakout_days=20, min_vol_lots=1500, min_amount_yi=1.0, use_ma_tangle=False, max_tangle_pct=5.0, require_chip_bonus=True):
    raw_market = fetch_all_tw_stocks_today()
    if not raw_market:
        return pd.DataFrame()
    candidates = list()
    bad = {"", "--", "---", "X", "None", "nan"}
    for it in raw_market:
        try:
            def to_f(v):
                s = str(v).replace(",", "").replace("+", "").strip()
                return float(s) if s not in bad else np.nan
            op, hi, lo, cl, df_p, vs, amt = to_f(it.get("open")), to_f(it.get("high")), to_f(it.get("low")), to_f(it.get("close")), to_f(it.get("change")), to_f(it.get("volume")), to_f(it.get("amount"))
            if np.isnan((op, hi, lo, cl, df_p, vs, amt)).any():
                continue
            v_lots, amt_yi = vs / 1000.0, amt / 100000000.0
            if v_lots < min_vol_lots or amt_yi < min_amount_yi:
                continue
            prev_c = cl - df_p
            if prev_c <= 0:
                continue
            chg = (df_p / prev_c) * 100.0
            if not (3.5 <= chg <= 8.5) or cl <= op:
                continue
            if ((hi - cl) / cl) * 100.0 >= 1.5 or (hi - cl) >= ((cl - op) / 3.0):
                continue
            candidates.append({"code": it.get("code"), "ticker": it.get("ticker"), "name": it.get("name"), "close": cl, "chg": chg, "v_lots": int(v_lots), "vs": vs, "amt_yi": round(amt_yi, 2)})
        except Exception:
            continue
    if not candidates:
        return pd.DataFrame()
    tickers = list()
    for c in candidates:
        tickers.append(c.get("ticker"))
    raw_hist = yf.download(tickers, period="5mo", group_by="ticker", progress=False, threads=True)
    start_dt = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    res_list = list()
    for cand in candidates:
        tk, code = cand.get("ticker"), cand.get("code")
        try:
            df = raw_hist[tk].dropna() if len(tickers) > 1 else raw_hist.dropna()
            if len(df) < 62:
                continue
            df = df.copy()
            df["MA5"], df["MA10"], df["MA20"], df["MA60"] = df["Close"].rolling(5).mean(), df["Close"].rolling(10).mean(), df["Close"].rolling(20).mean(), df["Close"].rolling(60).mean()
            df["V5"], df["V20"] = df["Volume"].rolling(5).mean(), df["Volume"].rolling(20).mean()
            td, yt = df.iloc[-1], df.iloc[-2]
            cl, vs = float(td["Close"]), float(td["Volume"])
            if not (cl > td["MA5"] and cl > td["MA10"] and cl > td["MA20"] and cl > td["MA60"]):
                continue
            if not (td["MA20"] > yt["MA20"] and td["MA60"] >= yt["MA60"]):
                continue
            if use_ma_tangle:
                mas = (td["MA5"], td["MA10"], td["MA20"])
                if ((max(mas) - min(mas)) / min(mas)) * 100.0 > max_tangle_pct:
                    continue
            if not (cl > df["Close"].iloc[-(breakout_days+1):-1].max()):
                continue
            pv5, pv20 = float(yt["V5"]), float(yt["V20"])
            if pv5 <= 0 or pv20 <= 0:
                continue
            v5_r, v20_r = vs / pv5, vs / pv20
            if not (vol_mult < v5_r < max_vol_mult and v20_r > 1.5):
                continue
            inst_net, m_diff, dt_sh, cap = fetch_single_chip_data(code, start_dt)
            dt_r = (dt_sh / cand.get("vs")) * 100.0 if (cand.get("vs") > 0 and dt_sh > 0) else 0.0
            if dt_r >= 45.0:
                continue
            to_pct = 0.0
            if cap > 0:
                to_pct = (cand.get("vs") / (cap / 10.0)) * 100.0
                if to_pct >= 10.0:
                    continue
            if require_chip_bonus and (inst_net <= 0 or m_diff >= cand.get("v_lots") * 0.15):
                continue
            df_chart = df.rename(columns={"Open": "open", "High": "max", "Low": "min", "Close": "close"})
            res_list.append({"代號": code, "名稱": cand.get("name"), "收盤價": round(cand.get("close"), 2), "漲跌幅(%)": round(cand.get("chg"), 2), "成交張數": cand.get("v_lots"), "金額(億)": cand.get("amt_yi"), "5日量比": round(v5_r, 2), "當沖比(%)": round(dt_r, 1), "週轉率(%)": round(to_pct, 2), "3日法人(張)": inst_net, "融資增減(張)": m_diff, "歷史資料": df_chart})
            time.sleep(0.1)
        except Exception:
            continue
    out = pd.DataFrame(res_list)
    if not out.empty:
        out = out.sort_values(by="3日法人(張)", ascending=False).reset_index(drop=True)
    return out
