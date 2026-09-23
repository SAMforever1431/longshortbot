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
    # OANDA
    # ========================================================

    def fetch_oanda(self):

        result = {
            "Source": "OANDA (Retail)",
            "Long %": "NaN",
            "Short %": "NaN",
            "Net Bias": "NaN",
            "Status": "Failed"
        }

        print("\n")
        print("=" * 60)
        print("OANDA RETAIL")
        print("=" * 60)

        token = self.config.get("oanda_token")
        env = self.config.get("oanda_env", "practice")

        # ----------------------------------------------------
        # Check environment variables
        # ----------------------------------------------------

        if token:
            print("✅ OANDA_TOKEN received")
        else:
            print("❌ OANDA_TOKEN is MISSING")

            result["Status"] = "Missing Token"
            return result

        print(f"ℹ️ OANDA environment: {env}")

        # ----------------------------------------------------
        # Select endpoint
        # ----------------------------------------------------

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

        print(f"🌐 Endpoint: {url}")
        print("📡 Requesting OANDA PositionBook...")

        # ----------------------------------------------------
        # Request
        # ----------------------------------------------------

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )

            print(
                f"HTTP Status: {response.status_code}"
            )

            # Print safe diagnostic information
            # without exposing token

            if response.status_code != 200:

                print(
                    "❌ OANDA returned an error:"
                )

                print(
                    response.text[:2000]
                )

                result["Status"] = (
                    f"HTTP {response.status_code}"
                )

                return result

            data = response.json()

            # ------------------------------------------------
            # Position book
            # ------------------------------------------------

            position_book = data.get(
                "positionBook"
            )

            if not position_book:

                print(
                    "❌ positionBook missing "
                    "from response"
                )

                print(
                    "Response keys:",
                    list(data.keys())
                )

                result["Status"] = (
                    "No PositionBook"
                )

                return result

            buckets = position_book.get(
                "buckets",
                []
            )

            print(
                f"✅ Received {len(buckets)} "
                "position buckets"
            )

            if not buckets:

                print(
                    "❌ No position buckets"
                )

                result["Status"] = (
                    "No Buckets"
                )

                return result

            # ------------------------------------------------
            # Calculate percentages
            # ------------------------------------------------

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

            print(
                f"✅ OANDA Long: {long_pct:.2f}%"
            )

            print(
                f"✅ OANDA Short: {short_pct:.2f}%"
            )

            print(
                f"✅ OANDA Bias: "
                f"{result['Net Bias']}"
            )

        except requests.exceptions.Timeout:

            print(
                "❌ OANDA request timed out"
            )

            result["Status"] = "Timeout"

        except requests.exceptions.RequestException as e:

            print(
                f"❌ OANDA request error: {e}"
            )

            result["Status"] = "Request Error"

        except Exception as e:

            print(
                f"❌ OANDA unexpected error: "
                f"{type(e).__name__}: {e}"
            )

            result["Status"] = "Exception"

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

        print("\n")
        print("=" * 60)
        print("CFTC COT")
        print("=" * 60)

        try:

            import cot_reports as cot

            current_year = (
                datetime.datetime.now().year
            )

            print(
                f"📅 Current year: {current_year}"
            )

            print(
                "📥 Downloading CFTC "
                "disaggregated futures data..."
            )

            df = cot.cot_year(
                current_year,
                cot_report_type="disaggregated_fut"
            )

            print(
                f"✅ CFTC dataframe received"
            )

            print(
                f"Rows: {len(df)}"
            )

            print(
                f"Columns: {len(df.columns)}"
            )

            # ------------------------------------------------
            # Check required column
            # ------------------------------------------------

            market_column = (
                "Market_and_Exchange_Names"
            )

            if market_column not in df.columns:

                print(
                    "❌ Required CFTC column "
                    "is missing:"
                )

                print(
                    market_column
                )

                print(
                    "Available columns:"
                )

                for column in df.columns:

                    print(
                        " -",
                        column
                    )

                result["Status"] = (
                    "Column Missing"
                )

                return result

            # ------------------------------------------------
            # Find gold
            # ------------------------------------------------

            gold_cot = df[
                df[
                    market_column
                ].astype(str).str.contains(
                    "GOLD - COMMODITY "
                    "EXCHANGE INC.",
                    case=False,
                    na=False
                )
            ]

            print(
                f"🥇 Gold rows found: "
                f"{len(gold_cot)}"
            )

            if gold_cot.empty:

                print(
                    "❌ GOLD contract not found"
                )

                # Show possible gold rows
                possible_gold = df[
                    df[
                        market_column
                    ].astype(str).str.contains(
                        "GOLD",
                        case=False,
                        na=False
                    )
                ]

                print(
                    "Possible GOLD contracts:"
                )

                for name in possible_gold[
                    market_column
                ].drop_duplicates().head(20):

                    print(
                        " -",
                        name
                    )

                result["Status"] = (
                    "Gold Not Found"
                )

                return result

            # ------------------------------------------------
            # Latest row
            # ------------------------------------------------

            latest = gold_cot.iloc[-1]

            # ------------------------------------------------
            # Check required columns
            # ------------------------------------------------

            long_column = (
                "M_Money_Positions_Long_All"
            )

            short_column = (
                "M_Money_Positions_Short_All"
            )

            if long_column not in df.columns:

                print(
                    f"❌ Missing column: "
                    f"{long_column}"
                )

                result["Status"] = (
                    "Long Column Missing"
                )

                return result

            if short_column not in df.columns:

                print(
                    f"❌ Missing column: "
                    f"{short_column}"
                )

                result["Status"] = (
                    "Short Column Missing"
                )

                return result

            # ------------------------------------------------
            # Extract Managed Money
            # ------------------------------------------------

            longs = float(
                latest[
                    long_column
                ]
            )

            shorts = float(
                latest[
                    short_column
                ]
            )

            total = longs + shorts

            print(
                f"Managed Money Long: "
                f"{longs}"
            )

            print(
                f"Managed Money Short: "
                f"{shorts}"
            )

            if total <= 0:

                print(
                    "❌ Total positions "
                    "is zero"
                )

                result["Status"] = (
                    "Invalid Positions"
                )

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

            print(
                f"✅ CFTC Long: "
                f"{long_pct:.2f}%"
            )

            print(
                f"✅ CFTC Short: "
                f"{short_pct:.2f}%"
            )

            print(
                f"✅ CFTC Bias: "
                f"{result['Net Bias']}"
            )

        except Exception as e:

            print(
                "❌ CFTC ERROR"
            )

            print(
                f"Type: {type(e).__name__}"
            )

            print(
                f"Message: {e}"
            )

            result["Status"] = (
                f"{type(e).__name__}"
            )

        return result


    # ========================================================
    # MYFXBOOK
    # ========================================================

    def fetch_myfxbook(self):

        result = {
            "Source": "Myfxbook (Retail)",
            "Long %": "NaN",
            "Short %": "NaN",
            "Net Bias": "NaN",
            "Status": "Failed"
        }

        print("\n")
        print("=" * 60)
        print("MYFXBOOK RETAIL")
        print("=" * 60)

        email = self.config.get(
            "myfxbook_email"
        )

        password = self.config.get(
            "myfxbook_password"
        )

        if not email:

            print(
                "❌ MYFXBOOK_EMAIL missing"
            )

            result["Status"] = (
                "Missing Email"
            )

            return result

        if not password:

            print(
                "❌ MYFXBOOK_PASSWORD missing"
            )

            result["Status"] = (
                "Missing Password"
            )

            return result

        print(
            "✅ Myfxbook credentials found"
        )

        try:

            # ------------------------------------------------
            # Login
            # ------------------------------------------------

            login_url = (
                "https://www.myfxbook.com/"
                "api/login.json"
            )

            print(
                "🔐 Logging into Myfxbook..."
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
                f"Login HTTP: "
                f"{login_response.status_code}"
            )

            login_response.raise_for_status()

            login_data = (
                login_response.json()
            )

            if login_data.get("error"):

                print(
                    "❌ Myfxbook login failed:"
                )

                print(
                    login_data.get(
                        "message"
                    )
                )

                result["Status"] = (
                    "Login Failed"
                )

                return result

            session = login_data.get(
                "session"
            )

            if not session:

                print(
                    "❌ No session received"
                )

                result["Status"] = (
                    "No Session"
                )

                return result

            print(
                "✅ Myfxbook login successful"
            )

            # ------------------------------------------------
            # Community Outlook
            # ------------------------------------------------

            outlook_url = (
                "https://www.myfxbook.com/"
                "api/get-community-outlook.json"
            )

            print(
                "📊 Requesting Community "
                "Outlook..."
            )

            outlook_response = requests.get(
                outlook_url,
                params={
                    "session": session
                },
                timeout=30
            )

            print(
                f"Outlook HTTP: "
                f"{outlook_response.status_code}"
            )

            outlook_response.raise_for_status()

            outlook_data = (
                outlook_response.json()
            )

            if outlook_data.get("error"):

                print(
                    "❌ Myfxbook outlook error:"
                )

                print(
                    outlook_data.get(
                        "message"
                    )
                )

                result["Status"] = (
                    "Outlook Failed"
                )

                return result

            symbols = outlook_data.get(
                "symbols",
                []
            )

            print(
                f"✅ Received "
                f"{len(symbols)} symbols"
            )

            # ------------------------------------------------
            # Find XAUUSD
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

                print(
                    "❌ XAUUSD not found"
                )

                result["Status"] = (
                    "XAUUSD Not Found"
                )

                return result

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

            print(
                f"✅ Myfxbook Long: "
                f"{long_pct:.2f}%"
            )

            print(
                f"✅ Myfxbook Short: "
                f"{short_pct:.2f}%"
            )

        except Exception as e:

            print(
                f"❌ Myfxbook Error: "
                f"{type(e).__name__}: {e}"
            )

        return result


    # ========================================================
    # RUN ALL
    # ========================================================

    def run_all(self):

        print("\n")
        print("#" * 60)
        print("# XAU/USD SENTIMENT AGGREGATOR")
        print("#" * 60)

        oanda = self.fetch_oanda()

        cftc = self.fetch_cftc_cot()

        myfxbook = self.fetch_myfxbook()

        return [
            oanda,
            cftc,
            myfxbook
        ]


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(
    bot_token,
    chat_id,
    text
):

    print("\n")
    print("=" * 60)
    print("TELEGRAM")
    print("=" * 60)

    if not bot_token:

        print(
            "❌ TELEGRAM_BOT_TOKEN missing"
        )

        return

    if not chat_id:

        print(
            "❌ TELEGRAM_CHAT_ID missing"
        )

        return

    print(
        "✅ Telegram credentials found"
    )

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

        if response.status_code != 200:

            print(
                response.text[:1000]
            )

        else:

            print(
                "✅ Telegram message sent"
            )

    except Exception as e:

        print(
            f"❌ Telegram Error: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    aggregator = FullXAUUSDScraper(
        config=CONFIG
    )

    data = aggregator.run_all()

    # --------------------------------------------------------
    # Build Telegram report
    # --------------------------------------------------------

    now = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    msg = (
        "📊 *XAU/USD SENTIMENT REPORT*\n"
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
                f" | Short: `{short_pct}%`\n"
            )

            msg += (
                f"└ Bias: "
                f"{bias_icon} *{bias}*\n"
            )

    # --------------------------------------------------------
    # Print final report
    # --------------------------------------------------------

    print("\n")
    print("#" * 60)
    print("# FINAL REPORT")
    print("#" * 60)

    print(msg)

    # --------------------------------------------------------
    # Telegram
    # --------------------------------------------------------

    send_telegram(
        CONFIG.get(
            "telegram_bot_token"
        ),

        CONFIG.get(
            "telegram_chat_id"
        ),

        msg
    )
