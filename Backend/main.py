from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from ingestion.models import SensorReadingInput
from ingestion.database import SessionLocal, engine, Base
from ingestion.database_models import Room, Reading, RiskAssessment, Alert
from typing import List
from datetime import datetime, timedelta
import json
import httpx
import joblib
import numpy as np


# ─────────────────────────────────────────────
# TELEGRAM CONFIG
# ─────────────────────────────────────────────
TELEGRAM_TOKEN = "8477835190:AAHZRP93-KQtrFVDo71pqKFzVzbPLQuj-wY"
TELEGRAM_CHAT_ID = "5910958826"

# One alert per room per 5 minutes — avoid spam
last_alert_time = {}


# ─────────────────────────────────────────────
# LOAD ML MODEL ON STARTUP
# Trained on Room 1 real ESP32 data only.
# Rooms 2 and 3 are simulated — they use
# IS 2189 rules directly, no ML.
# ─────────────────────────────────────────────
try:
    model = joblib.load("fire_model.pkl")
    print("ML model loaded successfully")
except FileNotFoundError:
    model = None
    print("WARNING: fire_model.pkl not found — run train_model.py first")


# ─────────────────────────────────────────────
# IS 2189 RULES — used for all rooms
# Called after ML flags an anomaly for Room 1
# Called directly for Rooms 2 and 3
# ─────────────────────────────────────────────
def is2189_check(temperature: float, gas_value: float):
    if gas_value >= 2000 or temperature >= 78:
        reasons = []
        if gas_value >= 2000:
            reasons.append("Gas critically high")
        if temperature >= 78:
            reasons.append("Temperature critically high")
        return "danger", ", ".join(reasons)
    else:
        reasons = []
        if gas_value >= 1000:
            reasons.append("Gas elevated")
        if temperature >= 57:
            reasons.append("Temperature elevated")
        reason = ", ".join(reasons) if reasons else "Unusual pattern detected"
        return "warning", reason


# ─────────────────────────────────────────────
# RISK ASSESSMENT — ML + IS 2189
#
# Room 1 (real ESP32):
#   Layer 1 — Isolation Forest trained on Room 1 data
#   Score > -0.08 → normal → SAFE
#   Score <= -0.08 → anomaly → check IS 2189
#   IS 2189 crossed → DANGER
#   IS 2189 not crossed → WARNING
#
# Rooms 2 and 3 (simulated):
#   IS 2189 only — no ML
#   gas >= 2000 OR temp >= 78 → DANGER
#   Otherwise → SAFE
#
# Layer 3 — Hardware (ESP32 buzzer)
#   Handles day 1 before model is trained
#   Completely offline — independent of this system
# ─────────────────────────────────────────────
def assess_risk(temperature: float, gas_value: float, motion: bool, room_id: int):

    # ── Rooms 2 and 3 — IS 2189 only, no ML ──
    if room_id != 1:
        if gas_value >= 2000 or temperature >= 78:
            reasons = []
            if gas_value >= 2000:
                reasons.append("Gas critically high")
            if temperature >= 78:
                reasons.append("Temperature critically high")
            return 0.9, "danger", ", ".join(reasons)
        return 0.0, "safe", "All readings normal"

    # ── Room 1 — ML + IS 2189 ──

    # If model not loaded fall back to IS 2189 only
    if model is None:
        if gas_value >= 2000 or temperature >= 78:
            return 0.9, "danger", "IS 2189 danger threshold crossed"
        return 0.0, "safe", "All readings normal (ML model not loaded)"

    # Prepare input — temperature and gas only
    # Motion removed from ML features — caused false warnings
    X = np.array([[temperature, gas_value]])

    # Get anomaly score
    # More negative = more anomalous
    score = model.decision_function(X)[0]
    
    

    if score > -0.05:
        # ML says normal for this building
        return 0.0, "safe", "All readings normal"

    # ML flagged anomaly — check severity in 3 tiers

    # Tier 1 — IS 2189 danger threshold
    if gas_value >= 2000 or temperature >= 78:
        reasons = []
        if gas_value >= 2000:
            reasons.append("Gas critically high")
        if temperature >= 78:
            reasons.append("Temperature critically high")
        return float(round(abs(score), 2)), "danger", ", ".join(reasons)

    # Tier 2 — physically normal range despite ML flag
    # ML can flag edge cases that are still safe in reality
    # if both temp and gas are within generous normal bounds
    elif temperature <= 45 and gas_value <= 1000:
        return 0.0, "safe", "All readings normal"

    # Tier 3 — elevated but below danger threshold
    else:
        reasons = []
        if gas_value >= 1000:
            reasons.append("Gas elevated")
        if temperature >= 57:
            reasons.append("Temperature elevated")
        reason = ", ".join(reasons) if reasons else "Unusual pattern detected"
        return float(round(abs(score), 2)), "warning", reason


# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────
async def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        })


# ─────────────────────────────────────────────
# CONNECTION MANAGER — WebSockets
# ─────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except:
                self.active_connections.remove(connection)

manager = ConnectionManager()


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fireflux.netlify.app", "http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────
# INGEST ENDPOINT
# ─────────────────────────────────────────────
@app.post("/ingest")
async def ingest(data: SensorReadingInput, db: Session = Depends(get_db)):

    # Step 1 — save raw reading
    reading = Reading(
        room_id=data.room_id,
        temperature=data.temperature,
        gas_value=data.gas_value,
        motion=data.motion
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    # Step 2 — assess risk
    # Room 1 → ML + IS 2189
    # Rooms 2/3 → IS 2189 only
    score, level, reason = assess_risk(
        data.temperature,
        data.gas_value,
        data.motion,
        data.room_id
    )

    # Step 3 — save risk assessment
    assessment = RiskAssessment(
        reading_id=reading.id,
        room_id=data.room_id,
        risk_score=score,
        risk_level=level,
        reason=reason
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    # Step 4 — if danger, create alert row
    alert = None
    if level == "danger":
        room = db.query(Room).filter(Room.id == data.room_id).first()
        alert = Alert(
            room_id=data.room_id,
            risk_assessment_id=assessment.id,
            message=f"Fire alert in {room.name}: {reason}",
            unsafe_exits=room.exits,
            notified=False
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

    # Step 5 — broadcast to all connected browsers
    await manager.broadcast({
        "room_id": data.room_id,
        "temperature": data.temperature,
        "gas_value": data.gas_value,
        "motion": data.motion,
        "risk_score": score,
        "risk_level": level,
        "reason": reason
    })

    # Step 6 — Telegram ONLY for danger
    # Warning shown on dashboard only — could be false alarm
    # Cooldown: one message per room per 5 minutes
    if level == "danger":
        now = datetime.now()
        last = last_alert_time.get(data.room_id)

        if last is None or (now - last) > timedelta(minutes=5):
            last_alert_time[data.room_id] = now

            message = (
                f"🚨 <b>FIREFLUX ALERT — DANGER</b>\n\n"
                f"🏢 Building: Building A\n"
                f"🚪 Room: {data.room_id}\n"
                f"⚠️ Reason: {reason}\n\n"
                f"🌡 Temperature: {data.temperature}°C\n"
                f"💨 Gas: {data.gas_value} ppm\n"
                f"👁 Motion: {'Yes' if data.motion else 'No'}\n\n"
                f"🚫 Check exits on dashboard\n\n"
                f"🕐 Time: {now.strftime('%H:%M:%S')}"
            )
            await send_telegram(message)

            # Mark alert as notified in database
            if alert:
                alert.notified = True
                db.commit()

    return {
        "status": "saved",
        "reading_id": reading.id,
        "risk_score": score,
        "risk_level": level,
        "reason": reason
    }


# ─────────────────────────────────────────────
# WEBSOCKET
# ─────────────────────────────────────────────
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ─────────────────────────────────────────────
# GET LATEST READING FOR A ROOM
# ─────────────────────────────────────────────
@app.get("/rooms/{room_id}/latest")
def get_latest(room_id: int, db: Session = Depends(get_db)):
    reading = (
        db.query(Reading)
        .filter(Reading.room_id == room_id)
        .order_by(Reading.timestamp.desc())
        .first()
    )

    if not reading:
        raise HTTPException(status_code=404, detail="No data for this room")

    assessment = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.reading_id == reading.id)
        .first()
    )

    return {
        "room_id": room_id,
        "temperature": reading.temperature,
        "gas_value": reading.gas_value,
        "motion": reading.motion,
        "timestamp": reading.timestamp.isoformat(),
        "risk_score": assessment.risk_score if assessment else 0,
        "risk_level": assessment.risk_level if assessment else "safe",
        "reason": assessment.reason if assessment else "All readings normal"
    }


# ─────────────────────────────────────────────
# GET HISTORY FOR A ROOM
# ─────────────────────────────────────────────
@app.get("/rooms/{room_id}/history")
def get_history(room_id: int, limit: int = 50, db: Session = Depends(get_db)):
    readings = (
        db.query(Reading)
        .filter(Reading.room_id == room_id)
        .order_by(Reading.timestamp.desc())
        .limit(limit)
        .all()
    )

    result = []
    for r in readings:
        assessment = (
            db.query(RiskAssessment)
            .filter(RiskAssessment.reading_id == r.id)
            .first()
        )
        result.append({
            "id": r.id,
            "temperature": r.temperature,
            "gas_value": r.gas_value,
            "motion": r.motion,
            "timestamp": r.timestamp.isoformat(),
            "risk_level": assessment.risk_level if assessment else "safe",
            "risk_score": assessment.risk_score if assessment else 0,
            "reason": assessment.reason if assessment else "All readings normal"
        })
    return result


# ─────────────────────────────────────────────
# GET ALL ROOMS
# ─────────────────────────────────────────────
@app.get("/rooms")
def get_rooms(db: Session = Depends(get_db)):
    rooms = db.query(Room).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "floor": r.floor,
            "exits": r.exits
        }
        for r in rooms
    ]


# ─────────────────────────────────────────────
# GET ACTIVE ALERTS
# ─────────────────────────────────────────────
@app.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    alerts = (
        db.query(Alert)
        .filter(Alert.notified == False)
        .order_by(Alert.created_at.desc())
        .all()
    )

    return [
        {
            "id": a.id,
            "room_id": a.room_id,
            "message": a.message,
            "unsafe_exits": a.unsafe_exits,
            "created_at": a.created_at.isoformat()
        }
        for a in alerts
    ]