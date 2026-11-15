import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# 內建台股上市+上櫃核心活躍股清單 (免連台灣官網抓名單，一年365天100%秒抓)
TW_STOCKS = {
    "2330.TW":"台積電","2317.TW":"鴻海","2454.TW":"聯發科","2382.TW":"廣達","2308.TW":"台達電","2881.TW":"富邦金","2882.TW":"國泰金","2891.TW":"中信金",
    "2303.TW":"聯電","3711.TW":"日月光投控","3231.TW":"緯創","2357.TW":"華碩","3017.TW":"奇鋐","3324.TWO":"雙鴻","2376.TW":"技嘉","6669.TW":"緯穎",
    "2603.TW":"長榮","2609.TW":"陽明","2615.TW":"萬海","2618.TW":"長榮航","2610.TW":"華航","2379.TW":"瑞昱","3034.TW":"聯詠","3008.TW":"大立光",
    "2327.TW":"國巨","2345.TW":"智邦","3661.TW":"世芯-KY","3443.TW":"創意","3533.TW":"嘉澤","1513.TW":"中興電","1519.TW":"華城","1503.TW":"士電",
    "1504.TW":"東元","2002.TW":"中鋼","1605.TW":"華新","2353.TW":"宏碁","2324.TW":"仁寶","4938.TW":"和碩","2301.TW":"光寶科","2356.TW":"英業達",
    "2409.TW":"友達","3481.TW":"群創","2344.TW":"華邦電","2408.TW":"南亞科","8299.TWO":"群聯","3260.TWO":"威剛","6239.TW":"力成","2449.TW":"京元電子",
    "3037.TW":"欣興","3189.TW":"景碩","8046.TW":"南電","2313.TW":"華通","2368.TW":"金像電","6274.TWO":"台燿","2383.TW":"台光電","3044.TW":"健鼎",
    "5483.TWO":"中美晶","6488.TWO":"環球晶","3105.TWO":"穩懋","8069.TWO":"元太","5347.TWO":"世界","3293.TWO":"鈊象","6510.TWO":"精測","5274.TWO":"信驊",
    "2474.TW":"可成","2354.TW":"鴻準","3005.TW":"神基","3706.TW":"神達","2377.TW":"微星","2421.TW":"建準","3653.TW":"健策","6285.TW":"啟碁",
    "5388.TW":"中磊","3596.TW":"智易","4968.TW":"立積","2458.TW":"義隆","3035.TW":"智原","6531.TW":"愛普*","2337.TW":"旺宏","3006.TW":"晶豪科",
    "4919.TW":"新唐","6770.TW":"力積電","5340.TWO":"建榮","1815.TWO":"富喬","8358.TWO":"金居","6182.TWO":"合晶","3532.TW":"台勝科","3707.TWO":"漢磊",
    "3016.TWO":"嘉晶","2360.TW":"致茂","6196.TW":"帆宣","3413.TW":"京鼎","3583.TW":"辛耘","3131.TWO":"弘塑","6640.TWO":"均華","5443.TWO":"均豪",
    "2464.TW":"盟立","2049.TW":"上銀","1590.TW":"亞德客-KY","4576.TW":"大銀微系統","2201.TW":"裕隆","2204.TW":"中華","1319.TW":"東陽","1522.TW":"堤維西",
    "2634.TW":"漢翔","8033.TW":"雷虎","2630.TW":"亞航","5284.TW":"jpp-KY","6446.TW":"藥華藥","6472.TW":"保瑞","1795.TW":"美時","4743.TWO":"合一",
    "9958.TW":"世紀鋼","3708.TW":"上緯投控","6806.TW":"森崴能源","1609.TW":"大亞","1608.TW":"華榮","2501.TW":"國建","2542.TW":"興富發","5522.TW":"遠雄",
    "2884.TW":"玉山金","2885.TW":"元大金","2886.TW":"兆豐金","2890.TW":"永豐金","2892.TW":"第一金","5880.TW":"合庫金","2883.TW":"凱基金","2887.TW":"台新金",
    "1101.TW":"台泥","1102.TW":"亞泥","1301.TW":"台塑","1303.TW":"南亞","1326.TW":"台化","6505.TW":"台塑化","1216.TW":"統一","2912.TW":"統一超",
    "2412.TW":"中華電","3045.TW":"台灣大","4904.TW":"遠傳","9910.TW":"豐泰","9904.TW":"寶成","1476.TW":"儒鴻","1477.TW":"聚陽","2105.TW":"正新",
    "2395.TW":"研華","6414.TW":"樺漢","3023.TW":"信邦","2492.TW":"華新科","3036.TW":"文曄","3702.TW":"大聯大","2347.TW":"聯強","8112.TW":"至上",
    "6176.TW":"瑞儀","2385.TW":"群光","2362.TW":"藍天","2404.TW":"漢唐","2455.TW":"全新","8086.TWO":"宏捷科","4977.TW":"眾達-KY","3163.TWO":"波若威",
    "3363.TWO":"上詮","6442.TW":"光聖","3081.TWO":"聯亞","4908.TWO":"前鼎","3450.TW":"聯鈞","2316.TW":"楠梓電","4958.TW":"臻鼎-KY","6153.TW":"嘉聯益",
    "5469.TW":"瀚宇博","6191.TW":"精成科","8155.TW":"博智","3715.TW":"定穎投控","2355.TW":"敬鵬","6213.TW":"聯茂","4927.TW":"泰鼎-KY","8039.TW":"台虹",
    "3376.TW":"新日興","6805.TW":"富世達","3548.TW":"兆利","1560.TW":"中砂","8028.TW":"昇陽半導體","3680.TWO":"家登","6187.TWO":"萬潤","3587.TWO":"閎康",
    "3289.TWO":"宜特","6683.TWO":"雍智科技","6515.TW":"穎崴","6223.TWO":"旺矽","3529.TWO":"力旺","6643.TWO":"M31","4966.TWO":"譜瑞-KY","5269.TW":"祥碩",
    "6415.TW":"矽力*-KY","3406.TW":"玉晶光","3019.TW":"亞光","4915.TW":"致伸","6202.TW":"盛群","8016.TW":"矽創","3545.TW":"敦泰","2388.TW":"威盛",
    "3227.TWO":"原相","6104.TWO":"創惟","5272.TWO":"笙科","4961.TW":"天鈺","3041.TW":"揚智","2436.TW":"偉詮電","6237.TWO":"驊訊","8261.TW":"富鼎",
    "5299.TWO":"杰力","6435.TWO":"大中","3317.TWO":"尼克森","2481.TW":"強茂","5425.TWO":"台半","3675.TWO":"德微","8255.TWO":"朋程","3552.TWO":"同致",
    "2231.TW":"為升","1536.TW":"和大","4551.TW":"智伸科","1524.TW":"耿鼎","6605.TW":"帝寶","2606.TW":"裕民","2605.TW":"新興","2637.TW":"慧洋-KY",
    "5608.TW":"四維航","2601.TW":"益航","2617.TW":"台航","2641.TWO":"正德","8936.TWO":"國統","6803.TWO":"崑鼎","9930.TW":"中聯資源","8422.TW":"可寧衛",
    "1717.TW":"長興","1722.TW":"台肥","1710.TW":"東聯","4755.TW":"三福化","1723.TW":"中碳","4763.TW":"材料-KY","4766.TW":"南寶","1773.TW":"勝一",
    "4770.TWO":"上品","3701.TW":"大眾控","2312.TW":"金寶","2352.TW":"佳世達","6206.TW":"飛捷","8114.TW":"振樺電","6412.TW":"群電","6282.TW":"康舒",
    "2328.TW":"廣宇","3013.TW":"晟銘電","6117.TWO":"迎廣","8210.TW":"勤誠","3693.TWO":"營邦","2059.TW":"川湖","3338.TW":"泰碩","2428.TW":"興勤",
    "6121.TWO":"新普","3211.TWO":"順達","4931.TWO":"新盛力","6781.TW":"AES-KY","3323.TWO":"加百裕","1582.TW":"信錦","6271.TW":"同欣電","3149.TW":"正達",
    "6147.TWO":"頎邦","8150.TW":"南茂","3264.TWO":"欣銓","6548.TWO":"長科*","8070.TW":"長華*","3374.TWO":"精材","6278.TW":"台表科","3030.TW":"德律"
}

def fetch_chip(stock_id, start_date):
    url, h = "https://finmindtrade.com", {"User-Agent": "Mozilla/5.0"}
    inst, m_diff, dt_sh, cap = 0, 0, 0.0, 0.0
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data"):
            df = pd.DataFrame(r.json().get("data"))
            df_r = df[df["date"].isin(sorted(df["date"].unique())[-3:])]
            inst = int((df_r["buy"].sum() - df_r["sell"].sum()) / 1000)
    except Exception: pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data") and len(r.json().get("data")) >= 2:
            df = pd.DataFrame(r.json().get("data")).sort_values("date").reset_index(drop=True)
            m_diff = int(df.iloc[-1]["MarginPurchaseTodayBalance"] - df.iloc[-2]["MarginPurchaseTodayBalance"])
    except Exception: pass
    try:
        r = requests.get(url, params={"dataset": "TaiwanStockDayTrading", "data_id": stock_id, "start_date": start_date}, headers=h, timeout=4)
        if r.status_code == 200 and r.json().get("data"):
            dt_sh = float(pd.DataFrame(r.json().get("data")).iloc[-1]["Volume"])
    except Exception: pass
    return inst, m_diff, dt_sh, cap

def run_screening(cfg):
    tks = list(TW_STOCKS.keys())
    stats = {"total": len(tks), "stage1": 0, "source": "內建上市櫃300+核心活躍股庫"}
    hist = yf.download(tks, period="5mo", group_by="ticker", progress=False, threads=True)
    sdt, res, k_pass = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"), list(), 0
    for tk in tks:
        code, name = tk.split(".").pop(0), TW_STOCKS[tk]
        try:
            df = hist[tk].copy() if isinstance(hist.columns, pd.MultiIndex) else hist.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close", "Volume"])
            if len(df) < 62: continue
            td, yt = df.iloc[-1], df.iloc[-2]
            op, hi, lo, cl, vs, pc = float(td["Open"]), float(td["High"]), float(td["Low"]), float(td["Close"]), float(td["Volume"]), float(yt["Close"])
            if pc <= 0: continue
            chg, vl, ay = ((cl - pc) / pc) * 100.0, vs / 1000.0, (cl * vs) / 100000000.0
            if cfg["use_liq"] and (vl < cfg["min_lots"] or ay < cfg["min_yi"]): continue
            if cfg["use_chg"] and (not (cfg["min_chg"] <= chg <= cfg["max_chg"]) or cl < op or (cl == op and cl < hi)): continue
            if cfg["use_shadow"] and (((hi - cl) / cl) * 100.0 >= 1.5 or (cl > op and (hi - cl) >= ((cl - op) / 3.0))): continue
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
            dt_r = (dt_sh / vs) * 100.0 if (vs > 0 and dt_sh > 0) else 0.0
            if cfg["use_liq"] and dt_r >= 45.0: continue
            if cfg["use_chip"] and (inst <= 0 or md >= vl * 0.15): continue
            res.append({"代號": code, "名稱": name, "收盤價": round(cl, 2), "漲跌幅(%)": round(chg, 2), "成交張數": int(vl), "金額(億)": round(ay, 2), "5日量比": round(v5_r, 2), "當沖比(%)": round(dt_r, 1), "週轉率(%)": "-", "3日法人(張)": inst, "融資增減(張)": md, "歷史資料": df.rename(columns={"Open": "open", "High": "max", "Low": "min", "Close": "close"})})
            time.sleep(0.05)
        except Exception: continue
    stats["stage1"] = k_pass
    out = pd.DataFrame(res)
    return (out.sort_values(by="5日量比", ascending=False).reset_index(drop=True) if not out.empty else out), stats
