import os
import requests
import time
import traceback
import re
from urllib.parse import quote

TARGET_DATE = "2026/05/17"
TARGET_DATE_END = "2026/05/18"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_PAGE = "https://eipro.jp/takachiho1/eventCalendars/index"
SEARCH_URL = "https://eipro.jp/takachiho1/eventCalendars/search"


BASE_VIEW = "https://eipro.jp/takachiho1/events/view/EV00000007"

last_available = set()

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_token(session):
    r = session.get(BASE_PAGE)
    r.raise_for_status()

    # simple & robust extraction (your confirmed HTML structure)
    start = r.text.find('name="action_token"')
    snippet = r.text[start:start+300]

    match = re.search(r'value="([^"]+)"', snippet)

    if not match:
        raise Exception("No action_token found")

    return match.group(1)

def build_link(slot):
    return (
        f"{BASE_VIEW}"
        f"?closable=1"
        f"&service_cd={slot['service_cd']}"
        f"&service_session_cd={slot['service_session_cd']}"
        f"&service_start_datetime={quote(slot['service_start_datetime'])}"
        f"&service_end_datetime={quote(slot['service_end_datetime'])}"
    )

def check(attempt_number):
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
    global last_available

    current_available = set()
    link_map = {}

    for s in slots:
        if TARGET_DATE not in s.get("service_start_datetime", ""):
            continue

        if (
            not s.get("fully_reserved_flg", True)
            or int(s.get("order_remain_amount", 0)) > 0
            or s.get("ordable") is True
        ):
            key = s["service_start_datetime"]
            current_available.add(key)
            link_map[key] = build_link(s)

    if current_available != last_available:

        added = current_available - last_available
        removed = last_available - current_available

        msg = "🚤 Availability change detected!\n\n"

        if added:
            msg += "🟢 NEW SLOTS:\n"
            for t in sorted(added):
                msg += f"{t}\n{link_map[t]}\n\n"

        if removed:
            msg += "🔴 REMOVED SLOTS:\n"
            for t in sorted(removed):
                msg += f"{t}\n"

        send_telegram(msg)

        last_available = current_available
    elif attempt_number % 60 == 0:
        msg = f"No change, but still alive. Attempt #{attempt_number}"
        send_telegram(msg)

def run(attempt_number):
    print(f"Attempt #{attempt_number}")
    try:
        check(attempt_number)
    except Exception as e:
        error_msg = (
            "⚠️ Takachiho checker error\n\n"
            f"{str(e)}\n\n"
            f"{traceback.format_exc()}"
        )
        send_telegram(error_msg)

if __name__ == "__main__":
    attempt_number = 0
    while True:
        run(attempt_number)
        attempt_number += 1
        time.sleep(60)  # 1 minutes