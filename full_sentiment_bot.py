import os
import json
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
# STATE FILE
# ============================================================

STATE_FILE = "sentiment_state.json"


# ============================================================
# STATE FUNCTIONS
# ============================================================

def load_previous_state():

    try:

        if not os.path.exists(STATE_FILE):

            print(
                "ℹ️ No previous state found. "
                "This is the first run."
            )

            return {}

        with open(
            STATE_FILE,
            "r"
        ) as f:

            state = json.load(f)

        print(
            "✅ Previous sentiment state loaded"
        )

        print(
            json.dumps(
                state,
                indent=2
            )
        )

        return state

    except Exception as e:

        print(
            f"⚠️ Could not load previous state: "
            f"{type(e).__name__}: {e}"
        )

        return {}


def save_current_state(data):

    state = {}

    for item in data:

        source = item.get(
            "Source"
        )

        if item.get(
            "Status"
        ) != "OK":

            continue

        state[source] = {
            "Long %": item.get(
                "Long %"
            ),

            "Short %": item.get(
                "Short %"
            )
        }

    try:

        with open(
            STATE_FILE,
            "w"
        ) as f:

            json.dump(
                state,
                f,
                indent=2
            )

        print(
            "✅ Current sentiment state saved"
        )

        print(
            json.dumps(
                state,
                indent=2
            )
        )

    except Exception as e:

        print(
            f"⚠️ Could not save state: "
            f"{type(e).__name__}: {e}"
        )


def percentage_change(
    current,
    previous
):

    if previous is None:

        return None

    try:

        current = float(
            current
        )

        previous = float(
            previous
        )

        return round(
            current - previous,
            2
        )

    except Exception:

        return None


def format_change(
    change
):

    if change is None:

        return ""

    if change > 0:

        return (
            f" ▲ +{change:.2f}%"
        )

    if change < 0:

        return (
            f" ▼ {change:.2f}%"
        )

    return (
        " → 0.00%"
    )


# ============================================================
# XAU/USD SENTIMENT AGGREGATOR
# ============================================================

class FullXAUUSDScraper:

    def __init__(
        self,
        config
    ):

        self.config = config


    # ========================================================
    # OANDA
    # ========================================================

    def fetch_oanda(self):

        result = {

            "Source":
                "OANDA (Retail)",

            "Long %":
                "NaN",

            "Short %":
                "NaN",

            "Net Bias":
                "NaN",

            "Status":
                "Failed"
        }

        print("\n")
        print("=" * 60)
        print("OANDA RETAIL")
        print("=" * 60)

        token = self.config.get(
            "oanda_token"
        )

        env = self.config.get(
            "oanda_env",
            "practice"
        )

        # ----------------------------------------------------
        # Token check
        # ----------------------------------------------------

        if not token:

            print(
                "❌ OANDA_TOKEN is missing"
            )

            result["Status"] = (
                "Missing Token"
            )

            return result

        print(
            "✅ OANDA_TOKEN received"
        )

        print(
            f"ℹ️ OANDA environment: "
            f"{env}"
        )

        # ----------------------------------------------------
        # Endpoint
        # ----------------------------------------------------

        if env == "practice":

            domain = (
                "api-fxpractice.oanda.com"
            )

        else:

            domain = (
                "api-fxtrade.oanda.com"
            )

        url = (
            f"https://{domain}"
            "/v3/instruments/"
            "XAU_USD/positionBook"
        )

        headers = {

            "Authorization":
                f"Bearer {token}",

            "Content-Type":
                "application/json"
        }

        print(
            f"🌐 Endpoint: {url}"
        )

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
                f"HTTP Status: "
                f"{response.status_code}"
            )

            if response.status_code != 200:

                print(
                    "❌ OANDA returned an error:"
                )

                print(
                    response.text[:2000]
                )

                result["Status"] = (
                    f"HTTP "
                    f"{response.status_code}"
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
                    "❌ positionBook missing"
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
                f"✅ Received "
                f"{len(buckets)} "
                f"position buckets"
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

            # ------------------------------------------------
            # Save result
            # ------------------------------------------------

            result.update({

                "Long %":
                    round(
                        long_pct,
                        2
                    ),

                "Short %":
                    round(
                        short_pct,
                        2
                    ),

                "Net Bias":
                    (
                        "LONG"
                        if long_pct >
                        short_pct
                        else "SHORT"
                    ),

                "Status":
                    "OK"
            })

            print(
                f"✅ OANDA Long: "
                f"{long_pct:.2f}%"
            )

            print(
                f"✅ OANDA Short: "
                f"{short_pct:.2f}%"
            )

            print(
                f"✅ OANDA Bias: "
                f"{result['Net Bias']}"
            )

        except requests.exceptions.Timeout:

            print(
                "❌ OANDA request timed out"
            )

            result["Status"] = (
                "Timeout"
            )

        except requests.exceptions.RequestException as e:

            print(
                f"❌ OANDA request error: "
                f"{e}"
            )

            result["Status"] = (
                "Request Error"
            )

        except Exception as e:

            print(
                f"❌ OANDA unexpected error: "
                f"{type(e).__name__}: {e}"
            )

            result["Status"] = (
                "Exception"
            )

        return result


    # ========================================================
    # CFTC COT
    # ========================================================

    def fetch_cftc_cot(self):

        result = {

            "Source":
                "CFTC COT (Inst.)",

            "Long %":
                "NaN",

            "Short %":
                "NaN",

            "Long Contracts":
                0,

            "Short Contracts":
                0,

            "Net Bias":
                "NaN",

            "Status":
                "Failed"
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
                f"📅 Current year: "
                f"{current_year}"
            )

            print(
                "📥 Downloading CFTC "
                "disaggregated futures data..."
            )

            df = cot.cot_year(

                current_year,

                cot_report_type=
                    "disaggregated_fut"
            )

            print(
                f"✅ CFTC dataframe received: "
                f"{len(df)} rows"
            )

            # ------------------------------------------------
            # Market column
            # ------------------------------------------------

            market_column = (
                "Market_and_Exchange_Names"
            )

            if market_column not in df.columns:

                print(
                    "❌ Market column missing"
                )

                result["Status"] = (
                    "Column Missing"
                )

                return result

            # ------------------------------------------------
            # Find Gold
            # ------------------------------------------------

            gold_cot = df[

                df[
                    market_column
                ]
                .astype(str)
                .str.contains(

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

                result["Status"] = (
                    "Gold Not Found"
                )

                return result

            # ------------------------------------------------
            # Latest Gold row
            # ------------------------------------------------

            latest = gold_cot.iloc[-1]

            # ------------------------------------------------
            # Managed Money columns
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
            # Contract counts
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

            total = (
                longs +
                shorts
            )

            print(
                f"Managed Money Long: "
                f"{longs:,.0f}"
            )

            print(
                f"Managed Money Short: "
                f"{shorts:,.0f}"
            )

            if total <= 0:

                print(
                    "❌ Invalid CFTC positions"
                )

                result["Status"] = (
                    "Invalid Positions"
                )

                return result

            # ------------------------------------------------
            # Percentages
            # ------------------------------------------------

            long_pct = (
                longs /
                total
            ) * 100

            short_pct = (
                shorts /
                total
            ) * 100

            # ------------------------------------------------
            # Save result
            # ------------------------------------------------

            result.update({

                "Long %":
                    round(
                        long_pct,
                        2
                    ),

                "Short %":
                    round(
                        short_pct,
                        2
                    ),

                "Long Contracts":
                    int(longs),

                "Short Contracts":
                    int(shorts),

                "Net Bias":
                    (
                        "LONG"
                        if longs >
                        shorts
                        else "SHORT"
                    ),

                "Status":
                    "OK"
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
                f"✅ CFTC Long Contracts: "
                f"{longs:,.0f}"
            )

            print(
                f"✅ CFTC Short Contracts: "
                f"{shorts:,.0f}"
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
                f"Type: "
                f"{type(e).__name__}"
            )

            print(
                f"Message: {e}"
            )

            result["Status"] = (
                type(e).__name__
            )

        return result


    # ========================================================
    # MYFXBOOK
    # ========================================================

    def fetch_myfxbook(self):

        result = {

            "Source":
                "Myfxbook (Retail)",

            "Long %":
                "NaN",

            "Short %":
                "NaN",

            "Long Positions":
                0,

            "Short Positions":
                0,

            "Net Bias":
                "NaN",

            "Status":
                "Failed"
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

        # ----------------------------------------------------
        # Credentials
        # ----------------------------------------------------

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

                    "email":
                        email,

                    "password":
                        password
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

            if login_data.get(
                "error"
            ):

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
                    "❌ No Myfxbook session"
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
                    "session":
                        session
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

            if outlook_data.get(
                "error"
            ):

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

            # ------------------------------------------------
            # Percentages
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

            # ------------------------------------------------
            # Actual position counts
            # ------------------------------------------------

            long_positions = int(
                xau.get(
                    "longPositions",
                    0
                )
            )

            short_positions = int(
                xau.get(
                    "shortPositions",
                    0
                )
            )

            # ------------------------------------------------
            # Save result
            # ------------------------------------------------

            result.update({

                "Long %":
                    round(
                        long_pct,
                        2
                    ),

                "Short %":
                    round(
                        short_pct,
                        2
                    ),

                "Long Positions":
                    long_positions,

                "Short Positions":
                    short_positions,

                "Net Bias":
                    (
                        "LONG"
                        if long_pct >
                        short_pct
                        else "SHORT"
                    ),

                "Status":
                    "OK"
            })

            print(
                f"✅ Myfxbook Long: "
                f"{long_pct:.2f}%"
            )

            print(
                f"✅ Myfxbook Short: "
                f"{short_pct:.2f}%"
            )

            print(
                f"✅ Myfxbook Long Positions: "
                f"{long_positions:,}"
            )

            print(
                f"✅ Myfxbook Short Positions: "
                f"{short_positions:,}"
            )

            print(
                f"✅ Myfxbook Bias: "
                f"{result['Net Bias']}"
            )

        except Exception as e:

            print(
                f"❌ Myfxbook Error: "
                f"{type(e).__name__}: {e}"
            )

            result["Status"] = (
                type(e).__name__
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

        oanda = (
            self.fetch_oanda()
        )

        cftc = (
            self.fetch_cftc_cot()
        )

        myfxbook = (
            self.fetch_myfxbook()
        )

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

        "chat_id":
            chat_id,

        "text":
            text,

        "parse_mode":
            "Markdown"
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

    # --------------------------------------------------------
    # Create aggregator
    # --------------------------------------------------------

    aggregator = FullXAUUSDScraper(
        config=CONFIG
    )

    # --------------------------------------------------------
    # Fetch all sources
    # --------------------------------------------------------

    data = (
        aggregator.run_all()
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Load previous state BEFORE saving current state
    # --------------------------------------------------------

    previous_state = (
        load_previous_state()
    )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    now = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------------
    # Telegram header
    # --------------------------------------------------------

    msg = (
        "📊 *XAU/USD SENTIMENT REPORT*\n"
        f"🕒 `{now}`\n"
        "━━━━━━━━━━━━━━━━━━━\n"
    )

    # --------------------------------------------------------
    # Build report
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # Bias icon
        # ----------------------------------------------------

        if bias == "LONG":

            bias_icon = "🟢"

        elif bias == "SHORT":

            bias_icon = "🔴"

        else:

            bias_icon = "⚪"

        # ----------------------------------------------------
        # Source heading
        # ----------------------------------------------------

        msg += (
            f"\n🔹 *{source}*\n"
        )

        # ----------------------------------------------------
        # Failed source
        # ----------------------------------------------------

        if status != "OK":

            msg += (
                f"⚠️ Status: `{status}`\n"
            )

            continue

        # ----------------------------------------------------
        # Previous values
        # ----------------------------------------------------

        previous = (
            previous_state.get(
                source,
                {}
            )
        )

        previous_long = (
            previous.get(
                "Long %"
            )
        )

        previous_short = (
            previous.get(
                "Short %"
            )
        )

        # ----------------------------------------------------
        # Percentage changes
        # ----------------------------------------------------

        long_change = (
            percentage_change(
                long_pct,
                previous_long
            )
        )

        short_change = (
            percentage_change(
                short_pct,
                previous_short
            )
        )

        long_change_text = (
            format_change(
                long_change
            )
        )

        short_change_text = (
            format_change(
                short_change
            )
        )

        # ====================================================
        # OANDA
        # ====================================================

        if source == "OANDA (Retail)":

            msg += (
                f"├ Long: `{long_pct}%`"
                f"{long_change_text}\n"
            )

            msg += (
                f"├ Short: `{short_pct}%`"
                f"{short_change_text}\n"
            )

        # ====================================================
        # CFTC
        # ====================================================

        elif source == "CFTC COT (Inst.)":

            long_contracts = item.get(
                "Long Contracts",
                0
            )

            short_contracts = item.get(
                "Short Contracts",
                0
            )

            msg += (
                f"├ Long: `{long_pct}%`"
                f"{long_change_text}"
                f" | `{long_contracts:,}` contracts\n"
            )

            msg += (
                f"├ Short: `{short_pct}%`"
                f"{short_change_text}"
                f" | `{short_contracts:,}` contracts\n"
            )

        # ====================================================
        # MYFXBOOK
        # ====================================================

        elif source == "Myfxbook (Retail)":

            long_positions = item.get(
                "Long Positions",
                0
            )

            short_positions = item.get(
                "Short Positions",
                0
            )

            msg += (
                f"├ Long: `{long_pct}%`"
                f"{long_change_text}"
                f" | `{long_positions:,}` positions\n"
            )

            msg += (
                f"├ Short: `{short_pct}%`"
                f"{short_change_text}"
                f" | `{short_positions:,}` positions\n"
            )

        # ====================================================
        # BIAS
        # ====================================================

        msg += (
            f"└ Bias: "
            f"{bias_icon} *{bias}*\n"
        )

    # --------------------------------------------------------
    # SAVE CURRENT STATE
    #
    # This happens AFTER the report is created.
    # Therefore:
    #
    # Previous run → Current run
    #
    # --------------------------------------------------------

    save_current_state(
        data
    )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print("\n")
    print("#" * 60)
    print("# FINAL TELEGRAM REPORT")
    print("#" * 60)

    print(
        msg
    )

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
