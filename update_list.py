import requests, pandas as pd, io, urllib3
urllib3.disable_warnings()

rows = list()
h = {"User-Agent": "Mozilla/5.0"}
for url, suffix in (("https://twse.com.tw", ".TW"), ("https://twse.com.tw", ".TWO")):
    try:
        r = requests.get(url, headers=h, timeout=20, verify=False)
        r.encoding = "big5"
        df = pd.read_html(io.StringIO(r.text))[0]
        for val in df[0].dropna():
            parts = str(val).strip().split()
            if len(parts) >= 2 and len(parts[0]) == 4 and parts[0].isdigit() and not parts[0].startswith("00"):
                rows.append({"code": parts[0], "ticker": f"{parts[0]}{suffix}", "name": parts[1]})
    except Exception as e:
        print("Error:", e)

if len(rows) > 1000:
    pd.DataFrame(rows).drop_duplicates(subset=["code"]).to_csv("tw_stocks.csv", index=False, encoding="utf-8-sig")
    print(f"成功儲存 {len(rows)} 檔台股總表！")
