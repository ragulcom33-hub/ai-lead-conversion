import json
import os
from datetime import datetime, timedelta, time
import pytz

from google.oauth2 import service_account
from googleapiclient.discovery import build

# 🔐 Load credentials from Render ENV
SERVICE_ACCOUNT_INFO = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))

SCOPES = ['https://www.googleapis.com/auth/calendar']

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=SCOPES
)

service = build('calendar', 'v3', credentials=credentials)

TIMEZONE = pytz.timezone("Asia/Kolkata")

WORK_START = 9
WORK_END = 18
LUNCH_START = 13
LUNCH_END = 14
SLOT_DURATION = 30  # minutes


# ---------------- GET BUSY TIMES ----------------
def get_busy_times(start, end):
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "items": [{"id": "ragulcom33@gmail.com"}]
    }

    result = service.freebusy().query(body=body).execute()
    return result['calendars']['ragulcom33@gmail.com']['busy']


# ---------------- CHECK FREE ----------------
def is_free(slot_start, slot_end, busy_times):
    for busy in busy_times:
        busy_start = datetime.fromisoformat(busy['start'])
        busy_end = datetime.fromisoformat(busy['end'])

        if slot_start < busy_end and slot_end > busy_start:
            return False
    return True


# ---------------- GET AVAILABLE SLOTS ----------------
def get_available_slots():
    slots = []
    now = datetime.now(TIMEZONE)
    day_offset = 0

    while len(slots) < 8:
        current_day = now + timedelta(days=day_offset)

        day_start = TIMEZONE.localize(datetime.combine(current_day.date(), time(0, 0)))
        day_end = TIMEZONE.localize(datetime.combine(current_day.date(), time(23, 59)))

        busy_times = get_busy_times(day_start, day_end)

        for hour in range(WORK_START, WORK_END):
            for minute in [0, 30]:

                # ❌ Skip lunch (1–2 PM)
                if LUNCH_START <= hour < LUNCH_END:
                    continue

                slot_start = TIMEZONE.localize(
                    datetime.combine(current_day.date(), time(hour, minute))
                )
                slot_end = slot_start + timedelta(minutes=SLOT_DURATION)

                if slot_start < now:
                    continue

                # ✅ Only add free slots
                if is_free(slot_start, slot_end, busy_times):
                    slots.append({
                        "label": slot_start.strftime("%d %b %I:%M %p"),
                        "value": slot_start.isoformat()
                    })

                if len(slots) >= 8:
                    break
            if len(slots) >= 8:
                break

        day_offset += 1

    return slots


# ---------------- BOOK SLOT ----------------
def book_slot(name, phone, slot_time):
    start = datetime.fromisoformat(slot_time)
    end = start + timedelta(minutes=30)

    # ✅ DOUBLE CHECK availability
    busy = get_busy_times(start, end)
    if busy:
        raise Exception("Slot already booked")

    event = {
        'summary': f'Appointment with {name}',
        'description': f'Phone: {phone}',
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
    }

    event_result = service.events().insert(
        calendarId='ragulcom33@gmail.com',
        body=event
    ).execute()

    return event_result.get('htmlLink')