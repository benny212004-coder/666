import os
import requests
from datetime import datetime
from screener import run_screening

def send_telegram_msg(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("未設定 Telegram 金鑰，跳過發送。")
        return
    url = f"https://telegram.org{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    df_res = run_screening(
        vol_mult=1.5,
        max_vol_mult=4.0,
        breakout_days=20,
        min_vol_lots=1500,
        min_amount_yi=1.0,
        use_ma_tangle=False,
        require_chip_bonus=True
    )
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if df_res.empty:
        msg = f"📅 *{today_str} 台股盤後動能雷達*\n\n今日無完全符合「均線翻揚＋防隔日沖＋籌碼健康」的突破標的。"
    else:
        lines = [f"🎯 *{today_str} 台股波段突破精選* 🎯\n(均線多頭翻揚 + 溫和帶量 + 法人買超)\n"]
        for _, r in df_res.iterrows():
            lines.append(
                f"• *{r['代號']} {r['名稱']}* | 收 `{r['收盤價']}` ({r['漲跌幅(%)']}%) | 量 `{r['成交張數']}張` ({r['5日量比']}倍) | 3日法人 `{r['3日法人(張)']}張`"
            )
        msg = "\n".join(lines)
        
    print(msg)
    send_telegram_msg(msg)
