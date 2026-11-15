import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BACKUP_UNIVERSE = (
    "2330.TW", "2317.TW", "2454.TW", "2382.TW", "2308.TW", "2881.TW", "2882.TW", "2891.TW",
    "2303.TW", "3711.TW", "3231.TW", "2357.TW", "3017.TW", "3324.TWO", "2376.TW", "6669.TW",
    "2603.TW", "2609.TW", "2615.TW", "2618.TW", "2610.TW", "2379.TW", "3034.TW", "3008.TW",
    "2327.TW", "2345.TW", "3661.TW", "3443.TW", "3533.TW", "1513.TW", "1519.TW", "1503.TW",
    "1504.TW", "2002.TW", "1605.TW", "2353.TW", "2324.TW", "4938.TW", "2301.TW", "2356.TW",
    "2409.TW", "3481.TW", "2344.TW", "2408.TW", "8299.TWO", "3260.TWO", "6239.TW", "2449.TW",
    "3037.TW", "3189.TW", "8046.TW", "2313.TW", "2368.TW", "6274.TWO", "2383.TW", "3044.TW",
    "5483.TWO", "6488.TWO", "3105.TWO", "8069.TWO", "5347.TWO", "3293.TWO", "6510.TWO", "5274.TWO"
)

def fetch_all_tw_stocks_today():
    all_s, h = list(), {"User-Agent": "Mozilla/5.0"}
    for url, is_tw in (("https://twse.com.tw", True), ("https://tpex.org.tw", False)):
        try:
            r = requests.get(url, headers=h, timeout=10, verify=False)
            if r.status_code == 200 and isinstance(r.json(), list):
                for it in r.json():
                    c = str(it.get("Code" if is_tw else "SecuritiesCompanyCode", "")).strip()
                    if len(c) == 4 and c.isdigit():
                        all_s.append({"code": c, "ticker": f"{c}.TW" if is_tw else f"{c}.TWO", "name": str(it.get("Name" if is_tw else "CompanyName", "")).strip(), "open": it.get("OpeningPrice" if is_tw else "Open", ""), "high": it.get("HighestPrice" if is_tw else "High", ""), "low": it.get("LowestPrice" if is_tw else "Low", ""), "close": it.get("ClosingPrice" if is_tw else "Close", ""), "change": it.get("Change", ""), "volume": it.get("TradeVolume" if is_tw else "TradingShares", ""), "amount": it.get("TradeValue" if is_tw else "TransactionAmount", "")})
        except Exception:
            pass
    return all_s

def fetch_chip(stock_id, start_date):
    url, h = "https://finmindtrade.com", {"User-Agent": "Mozilla/5.0"}
    inst, m_diff, dt_sh, cap = 0, 0, 0.0, 0.0
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=6)
        if r.status_code == 200 and r.json().get("data"):
            df = pd.DataFrame(r.json().get("data"))
            df_r = df[df["date"].isin(sorted(df["date"].unique())[-3:])]
            inst = int((df_r["buy"].sum() - df_r["sell"].sum()) / 1000)
    except Exception:
        pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=6)
        if r.status_code == 200 and r.json().get("data") and len(r.json().get("data")) >= 2:
            df = pd.DataFrame(r.json().get("data")).sort_values("date").reset_index(drop=True)
            m_diff = int(df.iloc[-1]["MarginPurchaseTodayBalance"] - df.iloc[-2]["MarginPurchaseTodayBalance"])
    except Exception:
        pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockDayTrading", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=6)
        if r.status_code == 200 and r.json().get("data"):
            dt_sh = float(pd.DataFrame(r.json().get("data")).iloc[-1]["Volume"])
    except Exception:
        pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInfo", "data_id": stock_id}, headers=h, timeout=6)
        if r.status_code == 200 and r.json().get("data"):
            d = r.json().get("data")
            row0 = next(iter(d)) if isinstance(d, list) else d
            if isinstance(row0, dict) and "capital_stock" in row0:
                cap = float(row0["capital_stock"])
    except Exception:
        pass
    return inst, m_diff, dt_sh, cap

def run_screening(vol_mult=1.5, max_vol_mult=4.0, breakout_days=20, min_vol_lots=1500, min_amount_yi=1.0, min_chg=3.5, max_chg=10.5, use_ma_tangle=False, max_tangle_pct=5.0, require_chip_bonus=True):
    stats = {"total": 0, "stage1": 0, "source": "官方全市場 OpenAPI"}
    raw = fetch_all_tw_stocks_today()
    cands = list()
    bad = {"", "--", "---", "X", "None", "nan"}
    if raw:
        stats["total"] = len(raw)
        for it in raw:
            try:
                to_f = lambda v: float(str(v).replace(",", "").replace("+", "").strip()) if str(v).replace(",", "").replace("+", "").strip() not in bad else np.nan
                op, hi, lo, cl, df_p, vs, amt = to_f(it.get("open")), to_f(it.get("high")), to_f(it.get("low")), to_f(it.get("close")), to_f(it.get("change")), to_f(it.get("volume")), to_f(it.get("amount"))
                if np.isnan((op, hi, lo, cl, df_p, vs, amt)).any(): continue
                vl, ay = vs / 1000.0, amt / 100000000.0
                if vl < min_vol_lots or ay < min_amount_yi or cl - df_p <= 0: continue
                chg = (df_p / (cl - df_p)) * 100.0
                if not (min_chg <= chg <= max_chg) or cl < op or (cl == op and cl < hi): continue
                if ((hi - cl) / cl) * 100.0 >= 1.5 or (cl > op and (hi - cl) >= ((cl - op) / 3.0)): continue
                cands.append({"code": it.get("code"), "ticker": it.get("ticker"), "name": it.get("name"), "close": cl, "chg": chg, "vl": int(vl), "vs": vs, "ay": round(ay, 2)})
            except Exception: continue
    else:
        stats["source"], stats["total"] = "雲端備援資料庫 (週末模式)", len(BACKUP_UNIVERSE)
        for tk in BACKUP_UNIVERSE:
            c = tk.split(".").pop(0)
            cands.append({"code": c, "ticker": tk, "name": c, "close": 0.0, "chg": 0.0, "vl": 0, "vs": 0.0, "ay": 0.0, "bk": True})

    stats["stage1"] = len(cands)
    if not cands: return pd.DataFrame(), stats
    tks = [c.get("ticker") for c in cands]
    hist = yf.download(tks, period="5mo", group_by="ticker", progress=False, threads=True)
    sdt = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    res = list()
    for cd in cands:
        tk, code = cd.get("ticker"), cd.get("code")
        try:
            df = hist[tk].dropna() if len(tks) > 1 else hist.dropna()
            if len(df) < 62: continue
            df = df.copy()
            for m in (5, 10, 20, 60): df[f"MA{m}"] = df["Close"].rolling(m).mean()
            df["V5"], df["V20"] = df["Volume"].rolling(5).mean(), df["Volume"].rolling(20).mean()
            td, yt = df.iloc[-1], df.iloc[-2]
            op, hi, cl, vs, pc = float(td["Open"]), float(td["High"]), float(td["Close"]), float(td["Volume"]), float(yt["Close"])
            if cd.get("bk"):
                if pc <= 0: continue
                chg, vl, ay = ((cl - pc) / pc) * 100.0, vs / 1000.0, (cl * vs) / 100000000.0
                if vl < min_vol_lots or ay < min_amount_yi or not (min_chg <= chg <= max_chg) or cl < op or (cl == op and cl < hi): continue
                if ((hi - cl) / cl) * 100.0 >= 1.5 or (cl > op and (hi - cl) >= ((cl - op) / 3.0)): continue
                cd["close"], cd["chg"], cd["vl"], cd["vs"], cd["ay"] = cl, chg, int(vl), vs, round(ay, 2)
            if not (cl > td["MA5"] and cl > td["MA10"] and cl > td["MA20"] and cl > td["MA60"]): continue
            if not (td["MA20"] > yt["MA20"] and td["MA60"] >= yt["MA60"]): continue
            if use_ma_tangle:
                mas = (td["MA5"], td["MA10"], td["MA20"])
                if ((max(mas) - min(mas)) / min(mas)) * 100.0 > max_tangle_pct: continue
            if not (cl > df["Close"].iloc[-(breakout_days+1):-1].max()): continue
            pv5, pv20 = float(yt["V5"]), float(yt["V20"])
            if pv5 <= 0 or pv20 <= 0 or not (vol_mult < vs / pv5 < max_vol_mult and vs / pv20 > 1.5): continue
            inst, md, dt_sh, cap = fetch_chip(code, sdt)
            dt_r = (dt_sh / cd.get("vs")) * 100.0 if (cd.get("vs") > 0 and dt_sh > 0) else 0.0
            to_p = (cd.get("vs") / (cap / 10.0)) * 100.0 if cap > 0 else 0.0
            if dt_r >= 45.0 or to_p >= 10.0: continue
            if require_chip_bonus and (inst <= 0 or md >= cd.get("vl") * 0.15): continue
            res.append({"代號": code, "名稱": cd.get("name"), "收盤價": round(cd.get("close"), 2), "漲跌幅(%)": round(cd.get("chg"), 2), "成交張數": cd.get("vl"), "金額(億)": cd.get("ay"), "5日量比": round(vs / pv5, 2), "當沖比(%)": round(dt_r, 1), "週轉率(%)": round(to_p, 2), "3日法人(張)": inst, "融資增減(張)": md, "歷史資料": df.rename(columns={"Open": "open", "High": "max", "Low": "min", "Close": "close"})})
            time.sleep(0.1)
        except Exception: continue
    out = pd.DataFrame(res)
    return (out.sort_values(by="3日法人(張)", ascending=False).reset_index(drop=True) if not out.empty else out), stats
