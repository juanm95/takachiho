import os
import requests

TARGET_DATE = "2026/05/16"
TARGET_DATE_END = "2026/05/17"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_PAGE = "https://eipro.jp/takachiho1/eventCalendars/index"
SEARCH_URL = "https://eipro.jp/takachiho1/eventCalendars/search"


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def get_token(session):
    r = session.get(BASE_PAGE)
    r.raise_for_status()

    # simple & robust extraction (your confirmed HTML structure)
    start = r.text.find('name="action_token"')
    snippet = r.text[start:start+300]

    import re
    match = re.search(r'value="([^"]+)"', snippet)

    if not match:
        raise Exception("No action_token found")

    return match.group(1)


def check():
    session = requests.Session()

    token = get_token(session)

    payload = {
        "data[conds][ServiceView][max_session_dateOver]": TARGET_DATE,
        "data[conds][ServiceView][min_session_dateUnder]": TARGET_DATE_END,
        "action_token": token,
        "root_action": "index",
        "calendar_view_name": "agendaWeek",
        "calendar_type": "week",
    }

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_PAGE,
        "User-Agent": "Mozilla/5.0",
    }

    r = session.post(SEARCH_URL, data=payload, headers=headers)
    r.raise_for_status()

    data = r.json()

    slots = data.get("results", [])

    available = []

    for s in slots:
        s["title"] = ""
        if TARGET_DATE not in s.get("service_start_datetime", ""):
            continue

        # KEY LOGIC
        if (
            not s.get("fully_reserved_flg", True)
            or int(s.get("order_remain_amount", 0)) > 0
            or s.get("ordable") is True
        ):
            available.append(s["service_start_datetime"])

    if available:
        msg = "🚤 Takachiho AVAILABLE!\n\n" + "\n".join(available)
        send_telegram(msg)
        print("AVAILABLE")
    else:
        send_telegram("Nope");
        print(data)


if __name__ == "__main__":
    check()