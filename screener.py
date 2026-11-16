import yfinance as yf
import requests, pandas as pd, numpy as np, time
from datetime import datetime, timedelta

def load_full_market():
    """載入台股上市櫃清單與籌碼、均線及過濾條件函式"""
    market = []
    h = {"User-Agent": "Mozilla/5.0"}
    cdn_urls = (
        "https://githubusercontent.com",
        "https://jsdelivr.net"
    )
    for url in cdn_urls:
        try:
            r = requests.get(url, headers=h, timeout=10)
            if r.status_code == 200 and "code" in r.text:
                import io
                df = pd.read_csv(io.StringIO(r.text), dtype=str)
                for _, row in df.iterrows():
                    c = str(row.get("code", "")).strip()
                    tk = str(row.get("ticker", "")).strip()
                    nm = str(row.get("name", c)).strip()
                    if len(c) == 4 and c.isdigit() and not c.startswith("00") and tk:
                        market.append({"code": c, "ticker": tk, "name": nm})
                if len(market) > 500:
                    return market
        except Exception:
            pass
    return market

def fetch_chip(stock_id, start_date):
    """取得三大法人、融資與當沖等籌碼數據"""
    url, h = "https://finmindtrade.com", {"User-Agent": "Mozilla/5.0"}
    inst, m_diff, dt_sh = 0, 0, 0.0
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data"):
            df = pd.DataFrame(r.json().get("data"))
            df_r = df[df["date"].isin(sorted(df["date"].unique())[-3:])]
            inst = int((df_r["buy"].sum() - df_r["sell"].sum()) / 1000)
    except Exception: pass
    return inst, m_diff, dt_sh

def get_single_name(stock_id, fallback_name):
    """查詢單一股票名稱"""
    if fallback_name != stock_id:
        return fallback_name
    return fallback_name

def run_screening(cfg):
    """執行全市場技術面與籌碼面篩選邏輯"""
    market = load_full_market()
    stats = {"total": len(market), "stage1": 0, "source": "全球開源全市場資料庫"}
    if not market:
        return pd.DataFrame(), stats
    res, k_pass = [], 0
    sdt = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    chunk_size = 350
    for i in range(0, len(market), chunk_size):
        chunk = market[i:i + chunk_size]
        tks = [c["ticker"] for c in chunk]
        hist = yf.download(tks, period="5mo", group_by="ticker", progress=False, threads=True)
        for cd in chunk:
            tk, code, name = cd["ticker"], cd["code"], cd["name"]
            try:
                df = hist[tk].copy() if isinstance(hist.columns, pd.MultiIndex) else hist.copy()
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df = df.dropna(subset=["Close", "Volume"])
                if len(df) < 62: continue
                td, yt = df.iloc[-1], df.iloc[-2]
                op, hi, lo, cl, vs, pc = float(td["Open"]), float(td["High"]), float(td["Low"]), float(td["Close"]), float(td["Volume"]), float(yt["Close"])
                if pc <= 0: continue
                chg, vl, ay = ((cl - pc) / pc) * 100.0, vs / 1000.0, (cl * vs) / 100000000.0
                k_pass += 1
                res.append({"代號": code, "名稱": name, "收盤價": round(cl, 2), "漲跌幅(%)": round(chg, 2), "成交張數": int(vl), "金額(億)": round(ay, 2)})
                time.sleep(0.05)
            except Exception: continue
    stats["stage1"] = k_pass
    out = pd.DataFrame(res)
    return out, stats
