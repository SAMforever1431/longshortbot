import os
import time
import datetime
import requests
import re
import pandas as pd
from playwright.sync_api import sync_playwright

# --- Config ---
CONFIG = {
    "oanda_token": "d38b07755c64c9cc317f0fa5cc7b17a3-a138e9540f606157d02533ab654afd4b",
    "oanda_env": "practice",
    "telegram_bot_token": "8753926739:AAGwaer6UNm8kP9e_eipaMqkGGfTzN_dqxY",
    "telegram_chat_id": "1341536286"
}

class FullXAUUSDScraper:
    def __init__(self, config):
        self.config = config

    def fetch_oanda(self):
        token = self.config.get("oanda_token")
        if not token:
            return {"Source": "OANDA (Retail)", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Status": "Skipped"}
        env = self.config.get("oanda_env", "practice")
        domain = "api-fxpractice.oanda.com" if env == "practice" else "api-fxtrade.oanda.com"
        url = f"https://{domain}/v3/instruments/XAU_USD/positionBook"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()["positionBook"]
                buckets = data["buckets"]
                long_pct = sum(float(b["longCountPercent"]) for b in buckets)
                short_pct = sum(float(b["shortCountPercent"]) for b in buckets)
                return {
                    "Source": "OANDA (Retail)",
                    "Long %": round(long_pct, 2),
                    "Short %": round(short_pct, 2),
                    "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                    "Status": "OK"
                }
        except Exception:
            pass
        return {"Source": "OANDA (Retail)", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Status": "Failed"}

    def fetch_cftc_cot(self):
        try:
            import cot_reports as cot
            current_year = datetime.datetime.now().year
            df = cot.cot_year(current_year, cot_report_type='disaggregated_fut')
            gold_cot = df[df['Market_and_Exchange_Names'].str.contains('GOLD - COMMODITY EXCHANGE INC.', na=False)]
            if gold_cot.empty:
                return {"Source": "CFTC COT (Inst.)", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Status": "No Data"}
            
            latest = gold_cot.iloc[-1]
            longs = float(latest['M_Money_Positions_Long_All'])
            shorts = float(latest['M_Money_Positions_Short_All'])
            total = longs + shorts
            long_pct = (longs / total) * 100 if total > 0 else 0
            short_pct = (shorts / total) * 100 if total > 0 else 0

            return {
                "Source": "CFTC COT (Inst.)",
                "Long %": round(long_pct, 2),
                "Short %": round(short_pct, 2),
                "Net Bias": "LONG" if longs > shorts else "SHORT",
                "Status": "OK"
            }
        except Exception:
            return {"Source": "CFTC COT (Inst.)", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Status": "Failed"}

    def fetch_browser_sentiments(self):
        myfx_data = {"Source": "Myfxbook (Retail)", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Status": "Failed"}
        investing_data = {"Source": "Investing.com", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Status": "Failed"}

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                
                # 1. Myfxbook Scrape
                try:
                    page.goto("https://www.myfxbook.com/community/outlook", timeout=60000)
                    page.wait_for_selector("text=XAUUSD", timeout=15000)
                    content = page.content()
                    
                    # Parsing percentages based on layout
                    long_match = re.search(r'XAUUSD.*?([\d\.]+)%\s*of the forex traders are going long', content, re.DOTALL | re.IGNORECASE)
                    if not long_match:
                        # Alternative table match fallback
                        long_match = re.search(r'XAUUSD.*?Long.*?(\d+(?:\.\d+)?)%', content, re.DOTALL | re.IGNORECASE)
                    
                    if long_match:
                        long_pct = float(long_match.group(1))
                        short_pct = round(100 - long_pct, 2)
                        myfx_data = {
                            "Source": "Myfxbook (Retail)",
                            "Long %": round(long_pct, 2),
                            "Short %": short_pct,
                            "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                            "Status": "OK"
                        }
                except Exception as e:
                    print(f"Myfxbook Playwright Error: {e}")

                # 2. Investing.com Scrape
                try:
                    page.goto("https://in.investing.com/currencies/xau-usd-scoreboard", timeout=60000)
                    page.wait_for_selector("text=Recent Sentiments", timeout=15000)
                    inv_content = page.content()
                    
                    # Extracting sentiment gauge info if available
                    bullish_match = re.search(r'([\d\.]+)%\s*Bullish', inv_content, re.IGNORECASE)
                    if bullish_match:
                        long_pct = float(bullish_match.group(1))
                        short_pct = round(100 - long_pct, 2)
                        investing_data = {
                            "Source": "Investing.com",
                            "Long %": round(long_pct, 2),
                            "Short %": short_pct,
                            "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                            "Status": "OK"
                        }
                except Exception as e:
                    print(f"Investing.com Playwright Error: {e}")

                browser.close()
        except Exception as e:
            print(f"Playwright general error: {e}")

        return myfx_data, investing_data

    def run_all(self):
        oanda = self.fetch_oanda()
        cot = self.fetch_cftc_cot()
        myfx, investing = self.fetch_browser_sentiments()
        return [oanda, cot, myfx, investing]

def send_telegram(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

if __name__ == "__main__":
    aggregator = FullXAUUSDScraper(config=CONFIG)
    data = aggregator.run_all()
    
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df = pd.DataFrame(data)
    print(df.to_string(index=False))
    
    # Format Telegram Message
    msg = f"📊 *COMPREHENSIVE XAU/USD REPORT*\n🕒 `{now}`\n━━━━━━━━━━━━━━━━━━━\n"
    for item in data:
        source = item.get("Source", "N/A")
        long_pct = item.get("Long %", "NaN")
        short_pct = item.get("Short %", "NaN")
        bias = item.get("Net Bias", "NaN")
        status = item.get("Status", "NaN")
        bias_icon = "🟢" if bias == "LONG" else "🔴" if bias == "SHORT" else "⚪"
        
        msg += f"\n🔹 *{source}*\n"
        if status != "OK":
            msg += f"⚠️ Status: `Failed / Blocked`\n"
        else:
            msg += f"├ Long: `{long_pct}%`  |  Short: `{short_pct}%`\n"
            msg += f"└ Bias: {bias_icon} *{bias}*\n"

    bot_token = CONFIG.get("telegram_bot_token")
    chat_id = CONFIG.get("telegram_chat_id")
    if bot_token and chat_id:
        send_telegram(bot_token, chat_id, msg)
