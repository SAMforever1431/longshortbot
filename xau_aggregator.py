import os
import time
import datetime
import threading
import requests
import pandas as pd
from http.server import HTTPServer, BaseHTTPRequestHandler

# Dummy Web Server Render Port Scan ko pass karne ke liye
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"XAU/USD Bot is running live!")

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

CONFIG = {
    "oanda_token": "d38b07755c64c9cc317f0fa5cc7b17a3-a138e9540f606157d02533ab654afd4b",
    "oanda_env": "practice",
    
    "myfxbook_email": "loudboiling.bhatt@gmail.com",
    "myfxbook_password": "Timmy#2013",
    
    "telegram_bot_token": "8753926739:AAGwaer6UNm8kP9e_eipaMqkGGfTzN_dqxY",
    "telegram_chat_id": "1341536286"
}

FETCH_INTERVAL = 900  # 15 Minutes

class XAUUSDPositionAggregator:
    def __init__(self, config):
        self.config = config

    def fetch_oanda(self):
        token = self.config.get("oanda_token")
        if not token:
            return {"Source": "OANDA", "Status": "Skipped"}

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
                    "Source": "OANDA",
                    "Long %": round(long_pct, 1),
                    "Short %": round(short_pct, 1),
                    "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                    "Timestamp": data.get("time", "")[:16].replace("T", " ")
                }
            return {"Source": "OANDA", "Status": f"Err {res.status_code}"}
        except Exception as e:
            return {"Source": "OANDA", "Status": "Failed"}

    def fetch_cftc_cot(self):
        try:
            import cot_reports as cot
            current_year = datetime.datetime.now().year
            df = cot.cot_year(current_year, cot_report_type='disaggregated_fut')
            
            gold_cot = df[df['Market_and_Exchange_Names'].str.contains('GOLD - COMMODITY EXCHANGE INC.', na=False)]
            if gold_cot.empty:
                return {"Source": "CFTC COT", "Status": "No Data"}

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
                "Source": "CFTC COT",
                "Long %": round(long_pct, 1),
                "Short %": round(short_pct, 1),
                "Net Bias": "NET LONG" if longs > shorts else "NET SHORT",
                "Timestamp": timestamp
            }
        except Exception as e:
            return {"Source": "CFTC COT", "Status": "Failed"}

    def fetch_myfxbook(self):
        email = self.config.get("myfxbook_email")
        password = self.config.get("myfxbook_password")
        if not email:
            return {"Source": "Myfxbook", "Status": "Skipped"}

        try:
            login_url = "https://www.myfxbook.com/api/login.json"
            login_res = requests.get(login_url, params={"email": email, "password": password}, timeout=10).json()
            
            if login_res.get("error"):
                return {"Source": "Myfxbook", "Status": "Auth Failed"}

            session = login_res["session"]
            outlook_url = f"https://www.myfxbook.com/api/get-community-outlook.json?session={session}"
            data = requests.get(outlook_url, timeout=10).json()
            requests.get(f"https://www.myfxbook.com/api/logout.json?session={session}", timeout=5)

            for item in data.get("symbols", []):
                if item["name"].upper() in ["XAUUSD", "GOLD"]:
                    long_pct = float(item["longPercentage"])
                    short_pct = float(item["shortPercentage"])
                    return {
                        "Source": "Myfxbook",
                        "Long %": round(long_pct, 1),
                        "Short %": round(short_pct, 1),
                        "Net Bias": "LONG" if long_pct > short_pct else "SHORT",
                        "Timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                    }
            return {"Source": "Myfxbook", "Status": "Not Found"}
        except Exception as e:
            return {"Source": "Myfxbook", "Status": "Failed"}

    def run_all(self):
        return [self.fetch_oanda(), self.fetch_cftc_cot(), self.fetch_myfxbook()]

def send_telegram(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

if __name__ == "__main__":
    # Web server ko background thread me start karein
    threading.Thread(target=start_dummy_server, daemon=True).start()
    
    aggregator = XAUUSDPositionAggregator(config=CONFIG)
    print("Starting XAU/USD Sentiment Telegram Dispatcher...")
    
    while True:
        try:
            data = aggregator.run_all()
            df = pd.DataFrame(data)
            
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg = f"📈 *XAU/USD Sentiment Update*\n`{now}`\n\n```\n{df.to_string(index=False)}\n```"
            
            bot_token = CONFIG.get("telegram_bot_token")
            chat_id = CONFIG.get("telegram_chat_id")
            
            if bot_token and chat_id:
                send_telegram(bot_token, chat_id, msg)
                print(f"[{now}] Message sent to Telegram successfully.")
            else:
                print("Missing Telegram credentials.")
                
        except Exception as e:
            print(f"Error in loop: {e}")
            
        time.sleep(FETCH_INTERVAL)
