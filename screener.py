import yfinance as yf
import requests, pandas as pd, numpy as np, time
from datetime import datetime, timedelta

def get_all_tickers():
    tks = []
    # 涵蓋台股上市(.TW)與上櫃(.TWO)全部4碼產業代號區間
    ranges = [(1101, 1817), (2002, 3716), (4102, 4999), (5201, 6875), (8011, 8996), (9902, 9958)]
    for s, e in ranges:
        for c in range(s, e + 1):
            tks.append(f"{c}.TW")
            tks.append(f"{c}.TWO")
    return tks

def fetch_chip_and_name(stock_id, start_date):
    url, h = "https://finmindtrade.com", {"User-Agent": "Mozilla/5.0"}
    inst, m_diff, dt_sh, name = 0, 0, 0.0, stock_id
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInfo", "data_id": stock_id}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data"):
            name = r.json()["data"][0].get("stock_name", stock_id)
    except Exception: pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data"):
            df = pd.DataFrame(r.json()["data"])
            df_r = df[df["date"].isin(sorted(df["date"].unique())[-3:])]
            inst = int((df_r["buy"].sum() - df_r["sell"].sum()) / 1000)
    except Exception: pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data") and len(r.json()["data"]) >= 2:
            df = pd.DataFrame(r.json()["data"]).sort_values("date").reset_index(drop=True)
            m_diff = int(df.iloc[-1]["MarginPurchaseTodayBalance"] - df.iloc[-2]["MarginPurchaseTodayBalance"])
    except Exception: pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockDayTrading", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data"):
            dt_sh = float(pd.DataFrame(r.json()["data"]).iloc[-1]["Volume"])
    except Exception: pass
    return inst, m_diff, dt_sh, name
def run_screening(cfg):
    all_tks = get_all_tickers()
    stats = {"total": 0, "stage1": 0, "source": "全台股上市櫃自動掃描引擎"}
    sdt = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    res, valid_cnt, k_pass = list(), 0, 0
    chunk_size = 500
    for i in range(0, len(all_tks), chunk_size):
        chunk = all_tks[i:i + chunk_size]
        hist = yf.download(chunk, period="5mo", group_by="ticker", progress=False, threads=True)
        for tk in chunk:
            code = tk.split(".").pop(0)
            try:
                if not isinstance(hist.columns, pd.MultiIndex):
                    continue
                if tk not in hist.columns.get_level_values(0):
                    continue
                df = hist[tk].dropna(subset=["Close", "Volume"])
                if len(df) < 62:
                    continue
                valid_cnt += 1
                td, yt = df.iloc[-1], df.iloc[-2]
                op, hi, lo, cl, vs, pc = float(td["Open"]), float(td["High"]), float(td["Low"]), float(td["Close"]), float(td["Volume"]), float(yt["Close"])
                if pc <= 0:
                    continue
                chg, vl, ay = ((cl - pc) / pc) * 100.0, vs / 1000.0, (cl * vs) / 100000000.0
                if cfg["use_liq"] and (vl < cfg["min_lots"] or ay < cfg["min_yi"]):
                    continue
                if cfg["use_chg"] and (not (cfg["min_chg"] <= chg <= cfg["max_chg"]) or cl < op or (cl == op and cl < hi)):
                    continue
                if cfg["use_shadow"] and (((hi - cl) / cl) * 100.0 >= 1.5 or (cl > op and (hi - cl) >= ((cl - op) / 3.0))):
                    continue
                k_pass += 1
                df = df.copy()
                for m in (5, 10, 20, 60):
                    df[f"MA{m}"] = df["Close"].rolling(m).mean()
                df["V5"], df["V20"] = df["Volume"].rolling(5).mean(), df["Volume"].rolling(20).mean()
                td, yt = df.iloc[-1], df.iloc[-2]
                if cfg["use_above_ma"] and not (cl > td["MA5"] and cl > td["MA10"] and cl > td["MA20"] and cl > td["MA60"]):
                    continue
                if cfg["use_ma_up"] and not (td["MA20"] > yt["MA20"] and td["MA60"] >= yt["MA60"]):
                    continue
                if cfg["use_tangle"]:
                    mas = (td["MA5"], td["MA10"], td["MA20"])
                    if ((max(mas) - min(mas)) / min(mas)) * 100.0 > cfg["max_tangle"]:
                        continue
                if cfg["use_brk"] and not (cl > df["Close"].iloc[-(cfg["brk_days"]+1):-1].max()):
                    continue
                pv5, pv20 = float(yt["V5"]), float(yt["V20"])
                if pv5 <= 0 or pv20 <= 0:
                    continue
                v5_r, v20_r = vs / pv5, vs / pv20
                if cfg["use_vol"] and not (cfg["min_v5"] < v5_r < cfg["max_v5"] and v20_r > 1.5):
                    continue
                inst, md, dt_sh, name = fetch_chip_and_name(code, sdt)
                dt_r = (dt_sh / vs) * 100.0 if (vs > 0 and dt_sh > 0) else 0.0
                if cfg["use_liq"] and dt_r >= 45.0:
                    continue
                if cfg["use_chip"] and (inst <= 0 or md >= vl * 0.15):
                    continue
                res.append({"代號": code, "名稱": name, "收盤價": round(cl, 2), "漲跌幅(%)": round(chg, 2), "成交張數": int(vl), "金額(億)": round(ay, 2), "5日量比": round(v5_r, 2), "當沖比(%)": round(dt_r, 1), "週轉率(%)": "-", "3日法人(張)": inst, "融資增減(張)": md, "歷史資料": df.rename(columns={"Open": "open", "High": "max", "Low": "min", "Close": "close"})})
                time.sleep(0.05)
            except Exception:
                continue
    stats["total"], stats["stage1"] = valid_cnt, k_pass
    out = pd.DataFrame(res)
    return (out.sort_values(by="5日量比", ascending=False).reset_index(drop=True) if not out.empty else out), stats
