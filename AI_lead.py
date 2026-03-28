from fastapi import FastAPI, Request
import requests
import os
import json
from typing import List
from datetime import datetime, timedelta, time
import pytz

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from db import get_user, create_user, update_user

# ---------------- GOOGLE CALENDAR SETUP ----------------
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/calendar']

SERVICE_ACCOUNT_INFO = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=SCOPES
)

CALENDAR_ID = "ragulcom33@gmail.com"

calendar_service = build('calendar', 'v3', credentials=credentials)

TIMEZONE = pytz.timezone("Asia/Kolkata")

WORK_START = 9
WORK_END = 18
LUNCH_START = 13
LUNCH_END = 14
SLOT_DURATION = 30


# ---------------- FASTAPI ----------------
app = FastAPI()

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_NUMBER = "whatsapp:+14155238886"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------- WEBHOOK ----------------
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    data = await request.form()

    user_msg = data.get("Body")
    user_number = data.get("From")

    print(f"Message from {user_number}: {user_msg}")

    reply = handle_flow(user_number, user_msg)

    send_whatsapp(user_number, reply)

    return "OK"


def send_whatsapp(to, message):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"

    requests.post(
        url,
        data={
            "From": TWILIO_NUMBER,
            "To": to,
            "Body": message
        },
        auth=(TWILIO_SID, TWILIO_AUTH)
    )


# ---------------- GOOGLE CALENDAR HELPERS ----------------
def get_busy_times(start, end):
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "items": [{"id": CALENDAR_ID}]
    }

    events = calendar_service.freebusy().query(body=body).execute()
    return events['calendars'][CALENDAR_ID]['busy']


def is_free(slot_start, slot_end, busy_times):
    for busy in busy_times:
        busy_start = datetime.fromisoformat(
            busy['start'].replace("Z", "+00:00")
        ).astimezone(TIMEZONE)

        busy_end = datetime.fromisoformat(
            busy['end'].replace("Z", "+00:00")
        ).astimezone(TIMEZONE)

        if slot_start < busy_end and slot_end > busy_start:
            return False
    return True


def get_available_slots():
    slots = []
    now = datetime.now(TIMEZONE)
    day_offset = 0

    while len(slots) < 8 and day_offset < 7:
        current_day = now + timedelta(days=day_offset)

        day_start = TIMEZONE.localize(datetime.combine(current_day.date(), time(0, 0)))
        day_end = TIMEZONE.localize(datetime.combine(current_day.date(), time(23, 59)))

        busy_times = get_busy_times(day_start, day_end)

        for hour in range(WORK_START, WORK_END):
            for minute in [0, 30]:

                # Skip lunch
                if LUNCH_START <= hour < LUNCH_END:
                    continue

                slot_start = TIMEZONE.localize(
                    datetime.combine(current_day.date(), time(hour, minute))
                )
                slot_end = slot_start + timedelta(minutes=SLOT_DURATION)

                if slot_start < now:
                    continue

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

    if not slots:
        print("⚠️ No slots found")

    print("SLOTS GENERATED:", slots)

    return slots


def book_slot(name, phone, slot_time):
    start = datetime.fromisoformat(slot_time)
    end = start + timedelta(minutes=30)

    # Double check availability
    busy = get_busy_times(start, end)
    if busy:
        raise Exception("Slot already taken")

    event = {
        'summary': f'Appointment with {name}',
        'description': f'Phone: {phone}',
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'},
    }

    calendar_service.events().insert(
        calendarId=CALENDAR_ID,
        body=event
    ).execute()


# ---------------- AI EXTRACTION ----------------
def extract_user_info(message: str):
    try:
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": """
Extract user details from the message.

Return ONLY JSON:
{
"name": "",
"phone": "",
"location": ""
}
"""
            },
            {"role": "user", "content": message}
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        return json.loads(response.choices[0].message.content)

    except:
        return {"name": "", "phone": "", "location": ""}


def ai_say(instruction: str, context: str = ""):
    try:
        messages = [
            {
                "role": "system",
                "content": f"""
You are a friendly WhatsApp assistant helping users book appointments.

Context:
{context}

Instruction:
{instruction}

Rules:
- Be natural and conversational
- Vary wording (avoid repetition)
- Keep it short
- Ask only ONE question
"""
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        return response.choices[0].message.content

    except:
        return "Let’s continue."


# ---------------- MAIN FLOW ----------------
def handle_flow(user: str, message: str):

    user_data = get_user(user)

    if not user_data:
        create_user(user)

    user_data = get_user(user)

    extracted = extract_user_info(message)

    if extracted.get("name"):
        update_user(user, "name", extracted["name"])

    if extracted.get("phone"):
        update_user(user, "phone", extracted["phone"])

    if extracted.get("location"):
        update_user(user, "place", extracted["location"])
        update_user(user, "state", "ready_for_slots")

    user_data = get_user(user)

    name = user_data[2]
    phone = user_data[3]
    place = user_data[4]
    state = user_data[1]

    print("USER STATE:", state)

    # Ask missing fields
    if not name:
        return ai_say("Ask for the user's name in a friendly way.")

    if not phone:
        return ai_say("Ask for phone number", f"User name is {name}")

    if not place:
        return ai_say("Ask for the user's location.")

    # SHOW SLOTS
    if state == "ready_for_slots":
        slots = get_available_slots()

        if not slots:
            return "No slots available right now. Please try later."

        update_user(user, "slots_json", json.dumps(slots))
        update_user(user, "state", "choosing_slot")

        user_data = get_user(user)  # refresh

        slot_text = "\n".join(
            [f"{i + 1}) {s['label']}" for i, s in enumerate(slots)]
        )

        return f"""Great! Here are available slots:

{slot_text}

👉 Reply with a number (1–{len(slots)}) to book your slot."""

    # SELECT SLOT
    if state == "choosing_slot":

        slots_json = user_data[5]

        if not slots_json:
            return "Something went wrong. Please try again."

        slots = json.loads(slots_json)

        try:
            choice = int(message.strip())
        except:
            return f"Please enter a valid number between 1 and {len(slots)}."

        if choice < 1 or choice > len(slots):
            return f"Invalid choice ❌\n\nPlease select a number between 1 and {len(slots)}."

        selected_slot = slots[choice - 1]

        try:
            book_slot(name, phone, selected_slot["value"])
        except:
            return "That slot was just booked 😅 Please choose another one."

        update_user(user, "state", "booked")

        return f"""✅ Booking confirmed!

📅 {selected_slot['label']}"""

    # AFTER BOOKING
    if state == "booked":
        update_user(user, "state", "booked_once")
        return "You're already booked."

    if state == "booked_once":
        update_user(user, "state", "")
        update_user(user, "name", "")
        update_user(user, "phone", "")
        update_user(user, "place", "")
        return "Welcome back! May I have your name?"

    return "Let’s continue."