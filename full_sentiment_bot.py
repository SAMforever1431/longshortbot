import os
import datetime
import requests


# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "oanda_token": os.getenv("OANDA_TOKEN"),
    "oanda_env": os.getenv("OANDA_ENV", "practice"),

    "myfxbook_email": os.getenv("MYFXBOOK_EMAIL"),
    "myfxbook_password": os.getenv("MYFXBOOK_PASSWORD"),

    "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
}


# ============================================================
# SENTIMENT AGGREGATOR
# ============================================================

class FullXAUUSDScraper:

    def __init__(self, config):
        self.config = config


    # ========================================================
    # OANDA RETAIL SENTIMENT
    # ========================================================

    def fetch_oanda(self):

        result = {
            "Source": "OANDA (Retail)",
            "Long %": "NaN",
            "Short %": "NaN",
            "Net Bias": "NaN",
            "Status": "Failed"
        }

        token = self.config.get("oanda_token")

        if not token:
            result["Status"] = "Missing Token"
            return result

        env = self.config.get(
            "oanda_env",
            "practice"
        )

        if env == "practice":
            domain = "api-fxpractice.oanda.com"
        else:
            domain = "api-fxtrade.oanda.com"

        url = (
            f"https://{domain}"
            "/v3/instruments/XAU_USD/positionBook"
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=20
            )

            print(
                f"OANDA HTTP Status: "
                f"{response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            position_book = data.get(
                "positionBook"
            )

            if not position_book:
                result["Status"] = "No Position Book"
                return result

            buckets = position_book.get(
                "buckets",
                []
            )

            if not buckets:
                result["Status"] = "No Buckets"
                return result

            long_pct = sum(
                float(
                    bucket.get(
                        "longCountPercent",
                        0
                    )
                )
                for bucket in buckets
            )

            short_pct = sum(
                float(
                    bucket.get(
                        "shortCountPercent",
                        0
                    )
                )
                for bucket in buckets
            )

            result.update({
                "Long %": round(long_pct, 2),
                "Short %": round(short_pct, 2),
                "Net Bias": (
                    "LONG"
                    if long_pct > short_pct
                    else "SHORT"
                ),
                "Status": "OK"
            })

        except Exception as e:

            print(
                f"OANDA Error: {e}"
            )

        return result


    # ========================================================
    # CFTC COT
    # ========================================================

    def fetch_cftc_cot(self):

        result = {
            "Source": "CFTC COT (Inst.)",
            "Long %": "NaN",
            "Short %": "NaN",
            "Net Bias": "NaN",
            "Status": "Failed"
        }

        try:

            import cot_reports as cot

            current_year = (
                datetime.datetime.now().year
            )

            print(
                "Downloading CFTC COT data..."
            )

            df = cot.cot_year(
                current_year,
                cot_report_type="disaggregated_fut"
            )

            gold_cot = df[
                df[
                    "Market_and_Exchange_Names"
                ].str.contains(
                    "GOLD - COMMODITY EXCHANGE INC.",
                    na=False
                )
            ]

            if gold_cot.empty:

                result["Status"] = "No Data"
                return result

            latest = gold_cot.iloc[-1]

            longs = float(
                latest[
                    "M_Money_Positions_Long_All"
                ]
            )

            shorts = float(
                latest[
                    "M_Money_Positions_Short_All"
                ]
            )

            total = longs + shorts

            if total <= 0:

                result["Status"] = "Invalid Data"
                return result

            long_pct = (
                longs / total
            ) * 100

            short_pct = (
                shorts / total
            ) * 100

            result.update({
                "Long %": round(
                    long_pct,
                    2
                ),
                "Short %": round(
                    short_pct,
                    2
                ),
                "Net Bias": (
                    "LONG"
                    if longs > shorts
                    else "SHORT"
                ),
                "Status": "OK"
            })

        except Exception as e:

            print(
                f"CFTC Error: {e}"
            )

        return result


    # ========================================================
    # MYFXBOOK RETAIL
    # ========================================================

    def fetch_myfxbook(self):

        result = {
            "Source": "Myfxbook (Retail)",
            "Long %": "NaN",
            "Short %": "NaN",
            "Net Bias": "NaN",
            "Status": "Failed"
        }

        email = self.config.get(
            "myfxbook_email"
        )

        password = self.config.get(
            "myfxbook_password"
        )

        if not email:

            result["Status"] = "Missing Email"
            return result

        if not password:

            result["Status"] = "Missing Password"
            return result

        try:

            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            login_url = (
                "https://www.myfxbook.com/"
                "api/login.json"
            )

            print(
                "Logging into Myfxbook..."
            )

            login_response = requests.get(
                login_url,
                params={
                    "email": email,
                    "password": password
                },
                timeout=30
            )

            print(
                f"Myfxbook Login HTTP: "
                f"{login_response.status_code}"
            )

            login_response.raise_for_status()

            login_data = (
                login_response.json()
            )

            if login_data.get("error"):

                result["Status"] = (
                    "Login Failed: "
                    + str(
                        login_data.get(
                            "message",
                            "Unknown"
                        )
                    )
                )

                return result

            session = login_data.get(
                "session"
            )

            if not session:

                result["Status"] = (
                    "No Session"
                )

                return result

            print(
                "Myfxbook login successful"
            )

            # ------------------------------------------------
            # COMMUNITY OUTLOOK
            # ------------------------------------------------

            outlook_url = (
                "https://www.myfxbook.com/"
                "api/get-community-outlook.json"
            )

            print(
                "Requesting Myfxbook "
                "Community Outlook..."
            )

            outlook_response = requests.get(
                outlook_url,
                params={
                    "session": session
                },
                timeout=30
            )

            print(
                f"Myfxbook Outlook HTTP: "
                f"{outlook_response.status_code}"
            )

            outlook_response.raise_for_status()

            outlook_data = (
                outlook_response.json()
            )

            if outlook_data.get("error"):

                result["Status"] = (
                    "Outlook Failed: "
                    + str(
                        outlook_data.get(
                            "message",
                            "Unknown"
                        )
                    )
                )

                return result

            symbols = outlook_data.get(
                "symbols",
                []
            )

            # ------------------------------------------------
            # FIND XAUUSD
            # ------------------------------------------------

            xau = None

            for symbol in symbols:

                name = str(
                    symbol.get(
                        "name",
                        ""
                    )
                ).upper().replace(
                    "/",
                    ""
                )

                if name == "XAUUSD":

                    xau = symbol
                    break

            if xau is None:

                result["Status"] = (
                    "XAUUSD Not Found"
                )

                return result

            # ------------------------------------------------
            # EXTRACT SENTIMENT
            # ------------------------------------------------

            long_pct = float(
                xau.get(
                    "longPercentage",
                    0
                )
            )

            short_pct = float(
                xau.get(
                    "shortPercentage",
                    0
                )
            )

            result.update({
                "Long %": round(
                    long_pct,
                    2
                ),
                "Short %": round(
                    short_pct,
                    2
                ),
                "Net Bias": (
                    "LONG"
                    if long_pct > short_pct
                    else "SHORT"
                ),
                "Status": "OK"
            })

        except Exception as e:

            print(
                f"Myfxbook Error: {e}"
            )

        return result


    # ========================================================
    # INVESTING.COM
    # ========================================================

    def fetch_investing(self):

        # We deliberately don't scrape Investing.com.
        #
        # GitHub Actions datacenter IPs are being blocked.
        # Returning a clean status is better than pretending
        # the data is valid.

        return {
            "Source": "Investing.com",
            "Long %": "NaN",
            "Short %": "NaN",
            "Net Bias": "NaN",
            "Status": "Unavailable"
        }


    # ========================================================
    # RUN EVERYTHING
    # ========================================================

    def run_all(self):

        print("\n")
        print("=" * 60)
        print("XAU/USD SENTIMENT AGGREGATOR")
        print("=" * 60)

        oanda = self.fetch_oanda()

        cot = self.fetch_cftc_cot()

        myfxbook = self.fetch_myfxbook()

        investing = self.fetch_investing()

        return [
            oanda,
            cot,
            myfxbook,
            investing
        ]


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(
    bot_token,
    chat_id,
    text
):

    if not bot_token:
        print(
            "Telegram bot token missing"
        )
        return

    if not chat_id:
        print(
            "Telegram chat ID missing"
        )
        return

    url = (
        "https://api.telegram.org/"
        f"bot{bot_token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=20
        )

        print(
            f"Telegram HTTP: "
            f"{response.status_code}"
        )

    except Exception as e:

        print(
            f"Telegram Error: {e}"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    aggregator = FullXAUUSDScraper(
        config=CONFIG
    )

    data = aggregator.run_all()

    now = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    msg = (
        "📊 *COMPREHENSIVE XAU/USD REPORT*\n"
        f"🕒 `{now}`\n"
        "━━━━━━━━━━━━━━━━━━━\n"
    )

    for item in data:

        source = item.get(
            "Source",
            "N/A"
        )

        long_pct = item.get(
            "Long %",
            "NaN"
        )

        short_pct = item.get(
            "Short %",
            "NaN"
        )

        bias = item.get(
            "Net Bias",
            "NaN"
        )

        status = item.get(
            "Status",
            "NaN"
        )

        if bias == "LONG":
            bias_icon = "🟢"

        elif bias == "SHORT":
            bias_icon = "🔴"

        else:
            bias_icon = "⚪"

        msg += (
            f"\n🔹 *{source}*\n"
        )

        if status != "OK":

            msg += (
                f"⚠️ Status: `{status}`\n"
            )

        else:

            msg += (
                f"├ Long: `{long_pct}%`"
                f"  |  Short: `{short_pct}%`\n"
            )

            msg += (
                f"└ Bias: "
                f"{bias_icon} *{bias}*\n"
            )

    print("\n")
    print("=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(msg)

    send_telegram(
        CONFIG.get(
            "telegram_bot_token"
        ),
        CONFIG.get(
            "telegram_chat_id"
        ),
        msg
    )
