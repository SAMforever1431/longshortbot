import os
import requests


MYFXBOOK_EMAIL = os.getenv("MYFXBOOK_EMAIL")
MYFXBOOK_PASSWORD = os.getenv("MYFXBOOK_PASSWORD")


def test_myfxbook():

    print("=" * 60)
    print("MYFXBOOK API TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Check credentials
    # --------------------------------------------------------

    if not MYFXBOOK_EMAIL:
        print("❌ MYFXBOOK_EMAIL is missing")
        return

    if not MYFXBOOK_PASSWORD:
        print("❌ MYFXBOOK_PASSWORD is missing")
        return

    print("✅ Myfxbook email found")
    print("✅ Myfxbook password found")

    # --------------------------------------------------------
    # STEP 1: LOGIN
    # --------------------------------------------------------

    login_url = "https://www.myfxbook.com/api/login.json"

    print("\n🔐 Logging into Myfxbook...")

    try:

        response = requests.get(
            login_url,
            params={
                "email": MYFXBOOK_EMAIL,
                "password": MYFXBOOK_PASSWORD
            },
            timeout=30
        )

        print(f"HTTP Status: {response.status_code}")

        response.raise_for_status()

        login_data = response.json()

    except Exception as e:

        print(f"❌ Login request failed: {e}")
        return

    # --------------------------------------------------------
    # Check login response
    # --------------------------------------------------------

    if login_data.get("error"):

        print("❌ Myfxbook login failed")
        print("Message:", login_data.get("message"))

        return

    session = login_data.get("session")

    if not session:

        print("❌ Login succeeded but no session was returned")
        print(login_data)

        return

    print("✅ Myfxbook login successful")
    print("✅ Session received")

    # --------------------------------------------------------
    # STEP 2: COMMUNITY OUTLOOK
    # --------------------------------------------------------

    outlook_url = (
        "https://www.myfxbook.com/api/"
        "get-community-outlook.json"
    )

    print("\n📊 Requesting Community Outlook...")

    try:

        response = requests.get(
            outlook_url,
            params={
                "session": session
            },
            timeout=30
        )

        print(f"HTTP Status: {response.status_code}")

        response.raise_for_status()

        outlook_data = response.json()

    except Exception as e:

        print(f"❌ Community Outlook request failed: {e}")
        return

    # --------------------------------------------------------
    # Check API error
    # --------------------------------------------------------

    if outlook_data.get("error"):

        print("❌ Myfxbook returned an error")
        print("Message:", outlook_data.get("message"))

        return

    # --------------------------------------------------------
    # Find XAUUSD
    # --------------------------------------------------------

    symbols = outlook_data.get("symbols", [])

    print(f"✅ Received {len(symbols)} symbols")

    xau = None

    for symbol in symbols:

        name = str(
            symbol.get("name", "")
        ).upper().replace("/", "")

        if name == "XAUUSD":

            xau = symbol
            break

    # --------------------------------------------------------
    # XAUUSD not found
    # --------------------------------------------------------

    if xau is None:

        print("\n❌ XAUUSD was not found")

        print("\nAvailable symbols:")

        for symbol in symbols:
            print(" -", symbol.get("name"))

        return

    # --------------------------------------------------------
    # Extract data
    # --------------------------------------------------------

    long_pct = float(
        xau.get("longPercentage", 0)
    )

    short_pct = float(
        xau.get("shortPercentage", 0)
    )

    long_positions = xau.get(
        "longPositions"
    )

    short_positions = xau.get(
        "shortPositions"
    )

    total_positions = xau.get(
        "totalPositions"
    )

    # --------------------------------------------------------
    # Display result
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("🎯 XAU/USD MYFXBOOK SENTIMENT")
    print("=" * 60)

    print(f"Long %          : {long_pct}%")
    print(f"Short %         : {short_pct}%")
    print(f"Long Positions  : {long_positions}")
    print(f"Short Positions : {short_positions}")
    print(f"Total Positions : {total_positions}")

    if long_pct > short_pct:
        bias = "LONG"
    elif short_pct > long_pct:
        bias = "SHORT"
    else:
        bias = "NEUTRAL"

    print(f"Bias            : {bias}")

    print("=" * 60)

    print("\n✅ MYFXBOOK TEST PASSED")


if __name__ == "__main__":
    test_myfxbook()
