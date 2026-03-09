from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, time, timedelta

import psycopg2
import psycopg2.extras
import os


# ======================================================
# CONFIG
# ======================================================

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

NGROK_URL = os.getenv("NGROK_URL")

DATABASE_URL = os.getenv("DATABASE_URL")

# Call time (hour, minute, second)
FIXED_CALL_TIME = time(15, 49, 0)


# ======================================================
# FASTAPI APP
# ======================================================

app = FastAPI()

@app.get("/")
def home():
    return {"status": "AI Insurance Voice Agent Running"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================
# TWILIO CLIENT
# ======================================================

twilio_client = Client(TWILIO_SID, TWILIO_AUTH)


# ======================================================
# DATABASE CONNECTION
# ======================================================


DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


# ======================================================
# CALL FUNCTION
# ======================================================

def trigger_call(customer_id, phone):

    twilio_client.calls.create(
        to=phone,
        from_=TWILIO_NUMBER,
        url=f"{NGROK_URL}/voice?customer_id={customer_id}"
    )

    print("Calling:", phone)


# ======================================================
# AUTO CALL ENGINE
# ======================================================

def enterprise_auto_call():

    print("Running scheduled call job")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT * FROM customers
        WHERE payment_status='pending'
    """)

    customers = cursor.fetchall()

    for customer in customers:

        trigger_call(customer["id"], customer["phone"])

        cursor.execute("""
            UPDATE customers
            SET last_call_date = NOW()
            WHERE id=%s
        """, (customer["id"],))

    conn.commit()

    cursor.close()
    conn.close()


# ======================================================
# VOICE HANDLER
# ======================================================

@app.post("/voice")
async def voice(request: Request):

    response = VoiceResponse()

    customer_id = request.query_params.get("customer_id")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM customers WHERE id=%s", (customer_id,))
    customer = cursor.fetchone()

    name = customer["name"]
    amount = customer["due_amount"]

    form = await request.form()
    speech = form.get("SpeechResult")

    if not speech:

        gather = Gather(
            input="speech",
            action=f"/voice?customer_id={customer_id}",
            method="POST"
        )

        gather.say(
            f"Hello {name}. Your insurance premium of {amount} rupees is due. "
            "Will you make the payment today?"
        )

        response.append(gather)

        response.say("No response received. Goodbye.")
        response.hangup()

        cursor.close()
        conn.close()

        return Response(str(response), media_type="application/xml")

    ai_reply = "Thank you for your response."

    cursor.execute("""
        INSERT INTO call_logs
        (customer_id, customer_text, ai_response, created_at)
        VALUES (%s,%s,%s,NOW())
    """, (customer_id, speech, ai_reply))

    conn.commit()

    cursor.close()
    conn.close()

    response.say(ai_reply)
    response.hangup()

    return Response(str(response), media_type="application/xml")


# ======================================================
# API ENDPOINTS
# ======================================================

@app.get("/customers")
def get_customers():

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM customers")
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return data


@app.get("/call-logs")
def get_logs():

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
        call_logs.id,
        customers.name as customer_name,
        customers.phone,
        call_logs.customer_text,
        call_logs.ai_response,
        call_logs.created_at
        FROM call_logs
        JOIN customers
        ON call_logs.customer_id = customers.id
        ORDER BY call_logs.created_at DESC
    """)

    logs = cursor.fetchall()

    cursor.close()
    conn.close()

    return logs


@app.post("/make-call/{customer_id}")
def make_call(customer_id: int):

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT phone FROM customers WHERE id=%s",(customer_id,))
    customer = cursor.fetchone()

    trigger_call(customer_id, customer["phone"])

    cursor.close()
    conn.close()

    return {"message":"call started"}


# ======================================================
# SCHEDULER
# ======================================================

scheduler = BackgroundScheduler()

def schedule_next_run():

    now = datetime.now()
    run_time = datetime.combine(now.date(), FIXED_CALL_TIME)

    if run_time < now:
        run_time += timedelta(days=1)

    scheduler.add_job(
        enterprise_auto_call,
        "date",
        run_date=run_time
    )

    print("Next call scheduled at:", run_time)


schedule_next_run()
scheduler.start()


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()