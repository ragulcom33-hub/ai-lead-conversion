import json
import os
from datetime import datetime, timedelta
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


# 📅 Get available slots (basic version)
def get_available_slots():
    now = datetime.utcnow()
    slots = []

    # Generate next 3 time slots (example)
    for i in range(1, 4):
        slot_time = now + timedelta(hours=i * 2)
        slots.append(slot_time.strftime("%Y-%m-%d %H:%M"))

    return slots


# 📅 Book appointment
def book_slot(name, phone, slot_str):
    start_time = datetime.strptime(slot_str, "%Y-%m-%d %H:%M")
    end_time = start_time + timedelta(hours=1)

    event = {
        'summary': f'Appointment with {name}',
        'description': f'Phone: {phone}',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
    }

    event_result = service.events().insert(
        calendarId='ragulcom33@gmail.com',
        body=event
    ).execute()

    return event_result.get('htmlLink')