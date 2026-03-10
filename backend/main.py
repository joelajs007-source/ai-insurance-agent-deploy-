from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from apscheduler.schedulers.background import BackgroundScheduler
import psycopg2
import psycopg2.extras
from datetime import datetime, time
from dotenv import load_dotenv
import os
import urllib.request

# ======================================================
# ================== LOAD ENV ==========================
# ======================================================

load_dotenv()

# ======================================================
# ================== CONFIG ============================
# ======================================================

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
NGROK_URL = os.getenv("NGROK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

MAX_CALLS_PER_DAY = 3
BUSINESS_START = time(7, 0)
BUSINESS_END = time(22, 0)

call_time_str = os.getenv("FIXED_CALL_TIME", "07:13")
h, m = map(int, call_time_str.split(":"))
FIXED_CALL_TIME = time(h, m)

# ======================================================
# ================== APP ===============================
# ======================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# ================== TWILIO INIT =======================
# ======================================================

twilio_client = None
if TWILIO_SID and TWILIO_AUTH:
    try:
        twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
        print("Twilio initialized")
    except Exception as e:
        print("Twilio init failed:", e)
else:
    print("Twilio credentials missing")

# ======================================================
# ================== DATABASE ==========================
# ======================================================

def get_db():
    return psycopg2.connect(DATABASE_URL)

# ======================================================
# ================== CALL FUNCTION =====================
# ======================================================

def trigger_call(customer_id, phone):
    if not twilio_client:
        print("Twilio not configured")
        return

    try:
        twilio_client.calls.create(
            to=phone,
            from_=TWILIO_NUMBER,
            url=f"{NGROK_URL}/voice?customer_id={customer_id}"
        )
        print(f"Calling customer {customer_id}")
    except Exception as e:
        print("Call failed:", e)

# ======================================================
# ================== KEEP ALIVE ========================
# ======================================================

def keep_alive():
    try:
        urllib.request.urlopen(f"{NGROK_URL}/")
        print("Keep alive ping sent")
    except:
        pass

# ======================================================
# ================== AUTO CALL ENGINE ==================
# ======================================================

def enterprise_auto_call():

    now = datetime.now()
    current_time = now.time()

    if current_time.hour != FIXED_CALL_TIME.hour or current_time.minute != FIXED_CALL_TIME.minute:
        return

    if not (BUSINESS_START <= current_time <= BUSINESS_END):
        print("Outside business hours")
        return

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        UPDATE customers
        SET daily_call_count = 0
        WHERE last_call_date IS NOT NULL
        AND last_call_date < CURRENT_DATE
    """)
    conn.commit()

    cursor.execute("""
        SELECT * FROM customers
        WHERE due_date <= CURRENT_DATE + INTERVAL '3 days'
        AND payment_status = 'pending'
        AND consent_flag = TRUE
        AND daily_call_count < %s
    """, (MAX_CALLS_PER_DAY,))

    customers = cursor.fetchall()

    for customer in customers:
        trigger_call(customer["id"], customer["phone"])

        cursor.execute("""
            UPDATE customers
            SET daily_call_count = daily_call_count + 1,
                last_call_date = CURRENT_DATE
            WHERE id = %s
        """, (customer["id"],))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Auto-called {len(customers)} customers")

# ======================================================
# ================== VOICE HANDLER =====================
# ======================================================

@app.post("/voice")
async def voice(request: Request):

    response = VoiceResponse()
    customer_id = request.query_params.get("customer_id")

    if not customer_id:
        response.say("Customer information missing.")
        response.hangup()
        return Response(str(response), media_type="application/xml")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM customers WHERE id = %s", (customer_id,))
    customer = cursor.fetchone()

    if not customer:
        cursor.close()
        conn.close()
        response.say("Customer not found.")
        response.hangup()
        return Response(str(response), media_type="application/xml")

    name = customer["name"]
    amount = customer["due_amount"]
    due_date = customer["due_date"].strftime("%d %B %Y")

    form = await request.form()
    speech_result = form.get("SpeechResult")

    # ================= FIRST MESSAGE =================
    if not speech_result:

        gather = Gather(
            input="speech",
            action=f"/voice?customer_id={customer_id}",
            method="POST",
            timeout=6,
            speech_timeout="auto"
        )

        professional_message = (
            f"Hello {name}. "
            f"This is a friendly reminder from your insurance provider. "
            f"Your premium amount of {amount} rupees is due on {due_date}. "
            f"Please confirm if you will complete the payment today."
        )

        gather.say(professional_message)
        response.append(gather)

        response.say("We did not receive any response. Thank you. Goodbye.")
        response.hangup()

        cursor.close()
        conn.close()

        return Response(str(response), media_type="application/xml")

    # ================= CUSTOMER RESPONSE =================

    customer_text = speech_result.strip()
    ai_reply = "Thank you for your response. We appreciate your time. Goodbye."

    cursor.execute("""
        INSERT INTO call_logs
        (customer_id, customer_text, ai_response,
         call_status, outcome, escalation_flag,
         created_at, intent_confidence, ai_summary, sentiment)
        VALUES (%s, %s, %s, 'completed', 'response_recorded', FALSE, %s, 1.0, %s, 'neutral')
    """, (
        customer_id,
        customer_text,
        ai_reply,
        datetime.now(),
        customer_text
    ))

    conn.commit()
    cursor.close()
    conn.close()

    response.say(ai_reply)
    response.hangup()

    return Response(str(response), media_type="application/xml")

# ======================================================
# ================== API ENDPOINTS =====================
# ======================================================

@app.get("/")
def home():
    return {"status": "Enterprise Auto Call System Running"}

@app.get("/customers")
def get_customers():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM customers ORDER BY id DESC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in data]

@app.get("/call-logs")
def call_logs():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM call_logs ORDER BY created_at DESC")
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in logs]

@app.post("/make-call/{customer_id}")
def make_call(customer_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT phone FROM customers WHERE id = %s", (customer_id,))
    customer = cursor.fetchone()
    cursor.close()
    conn.close()

    if not customer:
        return {"error": "Customer not found"}

    trigger_call(customer_id, customer["phone"])
    return {"message": "Call triggered successfully"}

# ======================================================
# ================== SCHEDULER =========================
# ======================================================

scheduler = BackgroundScheduler()
scheduler.add_job(enterprise_auto_call, "interval", minutes=1)
scheduler.add_job(keep_alive, "interval", minutes=14)
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()