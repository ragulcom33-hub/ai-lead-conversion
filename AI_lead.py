from fastapi import FastAPI, Request
import requests
import os
import json
from typing import List

from openai import OpenAI, APIError
from openai.types.chat import ChatCompletionMessageParam

from db import get_user, create_user, update_user
from calendar_service import get_available_slots, book_slot

app = FastAPI()

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_NUMBER = "whatsapp:+14155238886"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# -------------------- WEBHOOK --------------------
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


# -------------------- AI: EXTRACT USER DATA --------------------
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

If not present, keep empty.
"""
            },
            {
                "role": "user",
                "content": message
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        content = response.choices[0].message.content
        return json.loads(content)

    except APIError as e:
        print("OPENAI ERROR:", str(e))
        return {"name": "", "phone": "", "location": ""}

    except ValueError as e:
        print("JSON ERROR:", str(e))
        return {"name": "", "phone": "", "location": ""}


# -------------------- AI: SALES SPEAK --------------------
def ai_say(instruction: str):
    try:
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": f"""
You are a professional sales assistant.

Instruction:
{instruction}

Rules:
- Ask only ONE question
- Be friendly and professional
- Keep it short
- Do NOT repeat questions
"""
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        return response.choices[0].message.content

    except APIError as e:
        print("AI ERROR:", str(e))
        return "Let’s continue."

    except ValueError as e:
        print("VALUE ERROR:", str(e))
        return "Let’s continue."


# -------------------- MAIN FLOW --------------------
def handle_flow(user: str, message: str):

    user_data = get_user(user)

    # Create user if not exists
    if not user_data:
        create_user(user)
        user_data = get_user(user)

    # 🔹 Extract data using AI
    extracted = extract_user_info(message)

    if extracted.get("name"):
        update_user(user, "name", extracted["name"])

    if extracted.get("phone"):
        update_user(user, "phone", extracted["phone"])

    if extracted.get("location"):
        update_user(user, "place", extracted["location"])
        update_user(user, "state", "ready_for_slots")

    # Refresh user data
    user_data = get_user(user)

    name = user_data[2]
    phone = user_data[3]
    place = user_data[4]
    state = user_data[1]

    # ---------------- FLOW ----------------

    # ---------------- FLOW ----------------

    # Ask missing fields
    if not name:
        return ai_say("Ask for the user's name politely.")

    if not phone:
        return ai_say("Ask for the user's phone number politely.")

    if not place:
        return ai_say("Ask for the user's location.")

    # Show slots after all data collected
    if state == "ready_for_slots":
        update_user(user, "state", "choosing_slot")

        slots = get_available_slots()

        return f"""Great! Here are available slots:

    1. {slots[0]}
    2. {slots[1]}
    3. {slots[2]}

    Reply with 1, 2 or 3 to confirm your booking."""

    # Choosing slot
    if state == "choosing_slot":

        slots = get_available_slots()

        try:
            index = int(message.strip()) - 1
            slot = slots[index]
        except ValueError:
            return "Please choose a valid option (1, 2, or 3)."

        try:
            book_slot(name, phone, slot)
            print("BOOKED:", slot)
        except Exception as e:
            print("BOOKING ERROR:", str(e))
            return "Booking failed. Please try again."

        update_user(user, "state", "booked")

        return f"""✅ Your appointment is confirmed!

    📅 Slot: {slot}

    We look forward to speaking with you."""

    # Already booked
    if state == "booked":
        return "You're already booked. Let me know if you need anything!"