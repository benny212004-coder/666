import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time, urllib3, io

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_all_tw_universe():
    """一年365天全天候從證交所官方清單取得台股上市櫃全部普通股代號與中文名稱"""
    uni, h = list(), {"User-Agent": "Mozilla/5.0"}
    urls = (("https://twse.com.tw", ".TW"), ("https://twse.com.tw", ".TWO"))
    for url, suffix in urls:
        try:
            r = requests.get(url, headers=h, timeout=15, verify=False)
            r.encoding = "big5"
            dfs = pd.read_html(io.StringIO(r.text))
            if dfs:
                df = dfs[0]
                for val in df[0].dropna():
                    s = str(val).strip()
                    parts = s.split()
                    if len(parts) >= 2 and len(parts[0]) == 4 and parts[0].isdigit():
                        c, name = parts[0], parts[1]
                        if not c.startswith("00"):
                            uni.append({"code": c, "ticker": f"{c}{suffix}", "name": name})
        except Exception:
            pass
    return uni

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
        except Exception: pass
    return all_s

def fetch_chip(stock_id, start_date):
    url, h = "https://finmindtrade.com", {"User-Agent": "Mozilla/5.0"}
    inst, m_diff, dt_sh, cap = 0, 0, 0.0, 0.0
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=5)
        if r.status_code == 200 and r.json().get("data"):
            df = pd.DataFrame(r.json().get("data"))
            df_r = df[df["date"].isin(sorted(df["date"].unique())[-3:])]
            inst = int((df_r["buy"].sum() - df_r["sell"].sum()) / 1000)
    except Exception: pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=5)
        if r.status_code == 200 and r.json().get("data") and len(r.json().get("data")) >= 2:
            df = pd.DataFrame(r.json().get("data")).sort_values("date").reset_index(drop=True)
            m_diff = int(df.iloc[-1]["MarginPurchaseTodayBalance"] - df.iloc[-2]["MarginPurchaseTodayBalance"])
    except Exception: pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockDayTrading", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=5)
        if r.status_code == 200 and r.json().get("data"):
            dt_sh = float(pd.DataFrame(r.json().get("data")).iloc[-1]["Volume"])
    except Exception: pass
    return inst, m_diff, dt_sh, cap

def run_screening(cfg):
    stats = {"total": 0, "stage1": 0, "source": "官方全市場 OpenAPI"}
    raw, cands, bad = fetch_all_tw_stocks_today(), list(), {"", "--", "---", "X", "None", "nan"}
    is_backup = False
    if raw:
        stats["total"] = len(raw)
        for it in raw:
            try:
                to_f = lambda v: float(str(v).replace(",", "").replace("+", "").strip()) if str(v).replace(",", "").replace("+", "").strip() not in bad else np.nan
                op, hi, lo, cl, df_p, vs, amt = to_f(it.get("open")), to_f(it.get("high")), to_f(it.get("low")), to_f(it.get("close")), to_f(it.get("change")), to_f(it.get("volume")), to_f(it.get("amount"))
                if np.isnan((op, hi, lo, cl, df_p, vs, amt)).any() or cl - df_p <= 0: continue
                vl, ay, chg = vs / 1000.0, amt / 100000000.0, (df_p / (cl - df_p)) * 100.0
                if cfg["use_liq"] and (vl < cfg["min_lots"] or ay < cfg["min_yi"]): continue
                if cfg["use_chg"] and (not (cfg["min_chg"] <= chg <= cfg["max_chg"]) or cl < op or (cl == op and cl < hi)): continue
                if cfg["use_shadow"] and (((hi - cl) / cl) * 100.0 >= 1.5 or (cl > op and (hi - cl) >= ((cl - op) / 3.0))): continue
                cands.append({"code": it.get("code"), "ticker": it.get("ticker"), "name": it.get("name"), "close": cl, "chg": chg, "vl": int(vl), "vs": vs, "ay": round(ay, 2)})
            except Exception: continue
    else:
        is_backup = True
        full_uni = get_all_tw_universe()
        stats["source"], stats["total"] = "全市場雲端備援庫 (週末模式)", len(full_uni)
        for u in full_uni:
            cands.append({"code": u["code"], "ticker": u["ticker"], "name": u["name"], "close": 0.0, "chg": 0.0, "vl": 0, "vs": 0.0, "ay": 0.0, "bk": True})

    if not cands: return pd.DataFrame(), stats
    if not is_backup and len(cands) > 150: cands = sorted(cands, key=lambda x: x["ay"], reverse=True)[:150]
    
    sdt, res, k_pass = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"), list(), 0
    chunk_size = 300
    for i in range(0, len(cands), chunk_size):
        chunk = cands[i:i + chunk_size]
        tks = [c.get("ticker") for c in chunk]
        hist = yf.download(tks, period="5mo", group_by="ticker", progress=False, threads=True)
        for cd in chunk:
            tk, code = cd.get("ticker"), cd.get("code")
            try:
                df = hist[tk].copy() if isinstance(hist.columns, pd.MultiIndex) else hist.copy()
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df = df.dropna(subset=["Close", "Volume"])
                if len(df) < 62: continue
                td, yt = df.iloc[-1], df.iloc[-2]
                op, hi, lo, cl, vs, pc = float(td["Open"]), float(td["High"]), float(td["Close"]), float(td["Volume"]), float(yt["Close"])
                if cd.get("bk"):
                    if pc <= 0: continue
                    chg, vl, ay = ((cl - pc) / pc) * 100.0, vs / 1000.0, (cl * vs) / 100000000.0
                    if cfg["use_liq"] and (vl < cfg["min_lots"] or ay < cfg["min_yi"]): continue
                    if cfg["use_chg"] and (not (cfg["min_chg"] <= chg <= cfg["max_chg"]) or cl < op or (cl == op and cl < hi)): continue
                    if cfg["use_shadow"] and (((hi - cl) / cl) * 100.0 >= 1.5 or (cl > op and (hi - cl) >= ((cl - op) / 3.0))): continue
                    cd["close"], cd["chg"], cd["vl"], cd["vs"], cd["ay"] = cl, chg, int(vl), vs, round(ay, 2)
                k_pass += 1
                for m in (5, 10, 20, 60): df[f"MA{m}"] = df["Close"].rolling(m).mean()
                df["V5"], df["V20"] = df["Volume"].rolling(5).mean(), df["Volume"].rolling(20).mean()
                td, yt = df.iloc[-1], df.iloc[-2]
                if cfg["use_above_ma"] and not (cl > td["MA5"] and cl > td["MA10"] and cl > td["MA20"] and cl > td["MA60"]): continue
                if cfg["use_ma_up"] and not (td["MA20"] > yt["MA20"] and td["MA60"] >= yt["MA60"]): continue
                if cfg["use_tangle"] and ((max((td["MA5"], td["MA10"], td["MA20"])) - min((td["MA5"], td["MA10"], td["MA20"]))) / min((td["MA5"], td["MA10"], td["MA20"]))) * 100.0 > cfg["max_tangle"]: continue
                if cfg["use_brk"] and not (cl > df["Close"].iloc[-(cfg["brk_days"]+1):-1].max()): continue
                pv5, pv20 = float(yt["V5"]), float(yt["V20"])
                if pv5 <= 0 or pv20 <= 0: continue
                v5_r, v20_r = vs / pv5, vs / pv20
                if cfg["use_vol"] and not (cfg["min_v5"] < v5_r < cfg["max_v5"] and v20_r > 1.5): continue
                inst, md, dt_sh, cap = fetch_chip(code, sdt) if (cfg["use_liq"] or cfg["use_chip"]) else (0, 0, 0.0, 0.0)
                dt_r = (dt_sh / cd.get("vs")) * 100.0 if (cd.get("vs") > 0 and dt_sh > 0) else 0.0
                if cfg["use_liq"] and dt_r >= 45.0: continue
                if cfg["use_chip"] and (inst <= 0 or md >= cd.get("vl") * 0.15): continue
                res.append({"代號": code, "名稱": cd.get("name"), "收盤價": round(cd.get("close"), 2), "漲跌幅(%)": round(cd.get("chg"), 2), "成交張數": cd.get("vl"), "金額(億)": cd.get("ay"), "5日量比": round(v5_r, 2), "當沖比(%)": round(dt_r, 1), "週轉率(%)": "-", "3日法人(張)": inst, "融資增減(張)": md, "歷史資料": df.rename(columns={"Open": "open", "High": "max", "Low": "min", "Close": "close"})})
                time.sleep(0.05)
            except Exception: continue
    stats["stage1"] = k_pass
    out = pd.DataFrame(res)
    return (out.sort_values(by="5日量比", ascending=False).reset_index(drop=True) if not out.empty else out), stats
