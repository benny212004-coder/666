import requests, pandas as pd, io, urllib3
urllib3.disable_warnings()

rows = list()
h = {"User-Agent": "Mozilla/5.0"}

# 來源一：台灣證交所官方上市櫃代碼總表
for url, suffix in (("https://twse.com.tw", ".TW"), ("https://twse.com.tw", ".TWO")):
    try:
        r = requests.get(url, headers=h, timeout=20, verify=False)
        r.encoding = "big5"
        dfs = pd.read_html(io.StringIO(r.text))
        if dfs:
            df = dfs.pop(0)
            col0 = df.iloc[:, 0].dropna()
            for val in col0:
                parts = str(val).strip().split()
                if len(parts) >= 2:
                    c, name = parts.pop(0), parts.pop(0)
                    if len(c) == 4 and c.isdigit() and not c.startswith("00"):
                        rows.append({"code": c, "ticker": f"{c}{suffix}", "name": name})
    except Exception as e:
        print("ISIN Error:", e)

# 來源二（備援）：若證交所週末維護，改向 FinMind 取得台股上市櫃清單
if len(rows) < 500:
    try:
        r = requests.get("https://finmindtrade.com", params={"dataset": "TaiwanStockInfo"}, headers=h, timeout=15)
        d = r.json().get("data")
        if d:
            df = pd.DataFrame(d).drop_duplicates(subset=["stock_id"])
            for _, row in df.iterrows():
                c = str(row.get("stock_id", "")).strip()
                t = str(row.get("type", "")).strip()
                if len(c) == 4 and c.isdigit() and not c.startswith("00") and t in ("twse", "tpex"):
                    suffix = ".TW" if t == "twse" else ".TWO"
                    rows.append({"code": c, "ticker": f"{c}{suffix}", "name": str(row.get("stock_name", c)).strip()})
    except Exception as e:
        print("FinMind Error:", e)

df_out = pd.DataFrame(rows).drop_duplicates(subset=["code"]) if rows else pd.DataFrame(columns=["code", "ticker", "name"])
df_out.to_csv("tw_stocks.csv", index=False, encoding="utf-8-sig")
print(f"成功寫入 {len(df_out)} 檔台股總表！")
