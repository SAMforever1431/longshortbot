import os
import time
import datetime
import threading
import requests
import re
import pandas as pd
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import curl_cffi to bypass strict Cloudflare protection
try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

# --- Render Health Check Dummy Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"XAU/USD Bot is running live!")

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# --- Config ---
CONFIG = {
    "oanda_token": "d38b07755c64c9cc317f0fa5cc7b17a3-a138e9540f606157d02533ab654afd4b",
    "oanda_env": "practice",
    
    "telegram_bot_token": "8753926739:AAGwaer6UNm8kP9e_eipaMqkGGfTzN_dqxY",
    "telegram_chat_id": "1341536286"
}

# Auto-refresh interval (60 seconds = 1 minute)
FETCH_INTERVAL = 60  

class XAUUSDPositionAggregator:
    def __init__(self, config):
        self.config = config

    def fetch_oanda(self):
        token = self.config.get("oanda_token")
        if not token:
            return {"Source": "OANDA (Retail)", "Metric": "Position Book", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Timestamp": "NaN", "Status": "Skipped"}

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
                    "Metric": "Position Book",
                    "Long %": round(long_pct, 2),
                    "Short %": round(short_pct, 2),
                    "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                    "Timestamp": data.get("time", "")[:20],
                    "Status": "NaN"
                }
            return {"Source": "OANDA (Retail)", "Metric": "Position Book", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Timestamp": "NaN", "Status": f"Err {res.status_code}"}
        except Exception:
            return {"Source": "OANDA (Retail)", "Metric": "Position Book", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Timestamp": "NaN", "Status": "Failed"}

    def fetch_cftc_cot(self):
        try:
            import cot_reports as cot
            current_year = datetime.datetime.now().year
            df = cot.cot_year(current_year, cot_report_type='disaggregated_fut')
            
            gold_cot = df[df['Market_and_Exchange_Names'].str.contains('GOLD - COMMODITY EXCHANGE INC.', na=False)]
            if gold_cot.empty:
                return {"Source": "CFTC COT (Inst.)", "Metric": "Managed Money", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Timestamp": "NaN", "Status": "No Data"}

            date_col = next((col for col in gold_cot.columns if 'YYYY-MM-DD' in col or 'Date' in col), None)
            if date_col:
                gold_cot = gold_cot.copy()
                gold_cot['parsed_date'] = pd.to_datetime(gold_cot[date_col].astype(str), format='%y%m%d', errors='coerce')
                gold_cot = gold_cot.sort_values('parsed_date')
                latest = gold_cot.iloc[-1]
                timestamp = latest['parsed_date'].strftime('%Y-%m-%d')
            else:
                latest = gold_cot.iloc[-1]
                timestamp = "N/A"

            longs = float(latest['M_Money_Positions_Long_All'])
            shorts = float(latest['M_Money_Positions_Short_All'])
            total = longs + shorts
            long_pct = (longs / total) * 100 if total > 0 else 0
            short_pct = (shorts / total) * 100 if total > 0 else 0

            return {
                "Source": "CFTC COT (Inst.)",
                "Metric": "Managed Money",
                "Long %": round(long_pct, 2),
                "Short %": round(short_pct, 2),
                "Net Bias": "LONG" if longs > shorts else "SHORT",
                "Timestamp": timestamp,
                "Status": "NaN"
            }
        except Exception:
            return {"Source": "CFTC COT (Inst.)", "Metric": "Managed Money", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Timestamp": "NaN", "Status": "Failed"}

    def fetch_myfxbook(self):
        url = "https://www.myfxbook.com/community/outlook/XAUUSD"
        
        # Real Chrome browser headers to bypass Cloudflare 403 on Data Center IPs
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        
        try:
            if HAS_CFFI:
                res = cffi_requests.get(url, headers=browser_headers, impersonate="chrome120", timeout=25)
            else:
                res = requests.get(url, headers=browser_headers, timeout=25)

            if res.status_code != 200:
                return {"Source": "Myfxbook (Retail)", "Metric": "NaN", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Timestamp": "NaN", "Status": f"HTTP {res.status_code}"}

            html = res.text

            short_match = re.search(r'(\d+(?:\.\d+)?)%\s*of the forex traders are currently going short', html, re.IGNORECASE)
            long_match = re.search(r'(\d+(?:\.\d+)?)%\s*of the forex traders are going long', html, re.IGNORECASE)

            if short_match and long_match:
                short_pct = float(short_match.group(1))
                long_pct = float(long_match.group(1))
                return {
                    "Source": "Myfxbook (Retail)",
                    "Metric": "XAUUSD",
                    "Long %": round(long_pct, 2),
                    "Short %": round(short_pct, 2),
                    "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                    "Timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                    "Status": "NaN"
                }

            short_tbl = re.search(r'Short</span>\s*</td>\s*<td[^>]*>\s*(\d+(?:\.\d+)?)%', html, re.IGNORECASE)
            long_tbl = re.search(r'Long</span>\s*</td>\s*<td[^>]*>\s*(\d+(?:\.\d+)?)%', html, re.IGNORECASE)
            if short_tbl and long_tbl:
                short_pct = float(short_tbl.group(1))
                long_pct = float(long_tbl.group(1))
                return {
                    "Source": "Myfxbook (Retail)",
                    "Metric": "XAUUSD",
                    "Long %": round(long_pct, 2),
                    "Short %": round(short_pct, 2),
                    "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                    "Timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                    "Status": "NaN"
                }

        except Exception as e:
            print(f"[Myfxbook Exception] Error: {e}")

        return {"Source": "Myfxbook (Retail)", "Metric": "NaN", "Long %": "NaN", "Short %": "NaN", "Net Bias": "NaN", "Timestamp": "NaN", "Status": "Failed"}

    def run_all(self):
        return [self.fetch_oanda(), self.fetch_cftc_cot(), self.fetch_myfxbook()]

def format_telegram_message(data, timestamp):
    msg = f"📊 *XAU/USD SENTIMENT REPORT*\n🕒 `{timestamp}`\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n"
    
    for item in data:
        source = item.get("Source", "N/A")
        long_pct = item.get("Long %", "NaN")
        short_pct = item.get("Short %", "NaN")
        bias = item.get("Net Bias", "NaN")
        ts = item.get("Timestamp", "NaN")
        status = item.get("Status", "NaN")
        
        bias_icon = "🟢" if bias == "LONG" else "🔴" if bias == "SHORT" else "⚪"
        
        msg += f"\n🔹 *{source}*\n"
        if status != "NaN" and long_pct == "NaN":
            msg += f"⚠️ Status: `{status}`\n"
        else:
            msg += f"├ Long: `{long_pct}%`  |  Short: `{short_pct}%`\n"
            msg += f"├ Bias: {bias_icon} *{bias}*\n"
            msg += f"└ Time: `{ts}`\n"
            
    return msg

def send_telegram(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    
    aggregator = XAUUSDPositionAggregator(config=CONFIG)
    print("Starting XAU/USD Sentiment Telegram Dispatcher...")
    
    while True:
        try:
            data = aggregator.run_all()
            df = pd.DataFrame(data)
            
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n========================== XAU/USD SENTIMENT SUMMARY ({now}) ==========================")
            print(df.to_string(index=False))
            
            telegram_msg = format_telegram_message(data, now)
            
            bot_token = CONFIG.get("telegram_bot_token")
            chat_id = CONFIG.get("telegram_chat_id")
            
            if bot_token and chat_id:
                send_telegram(bot_token, chat_id, telegram_msg)
                print(f"\n[Auto-refreshing in {FETCH_INTERVAL} seconds... Message sent to Telegram]")
            else:
                print("Missing Telegram credentials.")
                
        except Exception as e:
            print(f"Error in loop: {e}")
            
        time.sleep(FETCH_INTERVAL)
