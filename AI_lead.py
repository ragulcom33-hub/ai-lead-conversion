from fastapi import FastAPI, Request
import requests
import os
from db import get_user, create_user, update_user
from calendar_service import get_available_slots, book_slot
from openai import OpenAI

app = FastAPI()

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_NUMBER = "whatsapp:+14155238886"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


# 🧠 AI FUNCTION
def get_ai_reply(user_message, context):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
                    You are a professional sales assistant for a business.

                    Your goal:
                    - Convert leads into booked appointments
                    - Speak politely, confidently, and persuasively
                    - Keep responses short and clear
                    - Ask for missing information (name, phone, location)
                    - Guide the user toward booking a slot

                    Tone:
                    - Friendly
                    - Helpful
                    - Slightly persuasive (like a salesperson)
                    - Not robotic

                    Context:
                    {context}
                    """
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        print("AI ERROR:", str(e))
        return "Sure, let's continue."


# 🔥 MAIN FLOW
def handle_flow(user, message):
    user_data = get_user(user)

    # FIRST MESSAGE
    if not user_data:
        create_user(user)
        update_user(user, "state", "asking_name")

        return get_ai_reply(
            message,
            "Greet user and ask for their name."
        )

    state = user_data[1]

    # ASK NAME
    if state == "asking_name":
        update_user(user, "name", message)
        update_user(user, "state", "asking_phone")

        return get_ai_reply(
            message,
            "User gave name. Ask for phone number politely."
        )

    # ASK PHONE
    elif state == "asking_phone":
        update_user(user, "phone", message)
        update_user(user, "state", "asking_place")

        return get_ai_reply(
            message,
            "Ask for user's location."
        )

    # ASK PLACE → SHOW SLOTS
    elif state == "asking_place":
        update_user(user, "place", message)
        update_user(user, "state", "choosing_slot")

        slots = get_available_slots()

        return get_ai_reply(
            message,
            f"""
User location received.

Now offer these slots:
1. {slots[0]}
2. {slots[1]}
3. {slots[2]}

Ask them to choose 1, 2 or 3.
"""
        )

    # SLOT SELECTION → BOOKING
    elif state == "choosing_slot":

        slots = get_available_slots()

        try:
            index = int(message.strip()) - 1
            slot = slots[index]
        except:
            return "Please choose a valid option (1, 2, or 3)."

        user_data = get_user(user)
        name = user_data[2]
        phone = user_data[3]

        try:
            book_slot(name, phone, slot)
            print("BOOKED:", slot)
        except Exception as e:
            print("BOOKING ERROR:", str(e))
            return "Booking failed. Please try again."

        update_user(user, "state", "booked")

        return get_ai_reply(
            message,
            f"Confirm booking for {slot} in a friendly professional tone."
        )

    # DONE
    else:
        return get_ai_reply(
            message,
            "User already booked. Respond politely."
        )