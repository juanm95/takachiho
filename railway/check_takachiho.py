import os
import requests
import time
import traceback
import re
from urllib.parse import quote
from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")

TARGET_DATE = "2026/05/16"
TARGET_DATE_END = "2026/05/17"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_PAGE = "https://eipro.jp/takachiho1/eventCalendars/index"
SEARCH_URL = "https://eipro.jp/takachiho1/eventCalendars/search"


BASE_VIEW = "https://eipro.jp/takachiho1/events/view/EV00000007"

MIN_HOUR = 10  # 10:00 AM or later only
REQUIRED_DAY = 16 

action_token = ""
last_available = set()

def is_quiet_hours():
    now = datetime.now(LOCAL_TZ)
    hour = now.hour

    quiet_hours = hour >= 23 or hour < 8
    if (quiet_hours):
        print("It's quiet hours")
    return quiet_hours

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_token(session):
    r = session.get(BASE_PAGE)
    print(f"get_token response length: {len(r.text) // 1000}k")
    print("--- SNIPPET START ---")
    print(r.text[:1000])
    print("--- SNIPPET END ---")
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
        f"&service_session_cd={slot['session_cd']}"
        f"&service_start_datetime={quote(slot['service_start_datetime'])}"
        f"&service_end_datetime={quote(slot['service_end_datetime'])}"
    )

def check(attempt_number):
    session = requests.Session()

    global action_token
    
    if(len(action_token) == 0):
        action_token = get_token(session)

    payload = {
        "data[conds][ServiceView][max_session_dateOver]": TARGET_DATE,
        "data[conds][ServiceView][min_session_dateUnder]": TARGET_DATE_END,
        "action_token": action_token,
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
    print(f"search response length: {len(r.text) // 1000}k")
    print("--- SNIPPET START ---")
    print(r.text[:1000])
    print("--- SNIPPET END ---")
    data = r.json()

    slots = data.get("results", [])
    global last_available

    current_available = set()
    link_map = {}

    for s in slots:
        if TARGET_DATE not in s.get("service_start_datetime", ""):
            continue

        start_dt = s["service_start_datetime"]
        hour = int(start_dt.split(" ")[1].split(":")[0])
        day = int(start_dt.split(" ")[0].split("/")[2])

        if hour < MIN_HOUR or day != REQUIRED_DAY:
            continue

        if (
            int(s.get("order_remain_amount", 0)) > 0
            and s.get("ordable") is True
        ):
            key = s["service_start_datetime"]
            current_available.add(key)
            link_map[key] = build_link(s)

    if current_available != last_available:

        msgs = []
        msgs.append("Currently available:")

        for t in sorted(current_available):
            msgs.append(f"{t}\n{link_map[t]}") 

        if (len(msgs) == 1):
            msgs.append("None")

        for msg in msgs:
            print(msg)
            send_telegram(msg)
            time.sleep(3)

        last_available = current_available
    elif attempt_number % 180 == 0 and not is_quiet_hours():
        msg = f"No change, but still alive. Attempt #{attempt_number}"
        send_telegram(msg)
        print(msg)

def run(attempt_number):
    print(f"Attempt #{attempt_number}")
    try:
        check(attempt_number)
        print(f"Done with attempt #{attempt_number}")
    except Exception as e:
        error_msg = (
            "⚠️ Takachiho checker error\n\n"
            f"{str(e)}\n\n"
            f"{traceback.format_exc()}"
        )
        global action_token
        action_token = ""
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    attempt_number = 0
    while True:
        run(attempt_number)
        attempt_number += 1
        time.sleep(60)  # 1 minutes