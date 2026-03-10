# 🔥 FireFlux — IoT Fire Detection & Response System

A real-time fire detection system built with ESP32, FastAPI, PostgreSQL, and Machine Learning.

*This project was originally conceptualized as a team project.
This repository contains my independent implementation of the system,
including backend architecture, database design, and deployment.

## Architecture

FireFlux uses a 3-layer detection architecture:

**Layer 1 — Hardware (ESP32)**
- DHT11 temperature sensor, MQ2 gas sensor, PIR motion sensor
- Onboard buzzer triggers immediately — works offline, no internet required
- Day-1 failsafe before ML model is trained

**Layer 2 — ML Anomaly Detection (Isolation Forest)**
- Trained on real sensor data from the building
- Learns building-specific normal — accounts for location, ventilation, season
- Flags unusual patterns even before fire thresholds are crossed
- Automatically adapts — retrain periodically as building conditions change

**Layer 3 — IS 2189 Rule-Based Detection**
- Indian Standard for fire detection and alarm systems
- Non-negotiable danger thresholds: gas ≥ 2000 ppm OR temperature ≥ 78°C
- Legally compliant, explainable, and location-independent

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Hardware | ESP32, DHT11, MQ2, PIR |
| Backend | FastAPI, Python |
| Database | PostgreSQL, SQLAlchemy |
| ML | Scikit-learn, Isolation Forest |
| Real-time | WebSockets |
| Notifications | Telegram Bot API |
| Frontend | HTML, CSS, JavaScript, Leaflet.js |
| Deployment | Docker, Render, Superbase |

## Features

- 📡 Real-time sensor data ingestion from ESP32
- 🤖 ML anomaly detection trained on building-specific data
- 🚨 Instant Telegram alerts on danger with 5-minute cooldown
- 🗺️ Live city dashboard with map markers per building
- 📊 Per-room rolling history timeline
- 🔬 Simulator panel for demo without hardware
- 🐳 Dockerized for cloud deployment

## Risk Assessment Logic

```
Room 1 (real ESP32) — ML + IS 2189
  ML score > -0.05                     → SAFE
  ML flags + gas >= 2000 / temp >= 78  → DANGER
  ML flags + temp <= 45 & gas <= 1000  → SAFE (physical bounds check)
  ML flags + elevated values           → WARNING

Rooms 2/3 (simulated) — IS 2189 only
  gas >= 2000 OR temp >= 78            → DANGER
  otherwise                            → SAFE
```

## Project Structure

```
Fireflux_fnl/
├── Backend/
│   ├── main.py              # FastAPI app, WebSockets, Telegram
│   ├── train_model.py       # ML training script
│   ├── requirements.txt
│   ├── Dockerfile
│   └── ingestion/
│       ├── database.py      # SQLAlchemy engine
│       ├── database_models.py
│       └── models.py        # Pydantic schemas
└── Frontend/
    ├── index.html           # City dashboard with map
    ├── buildingA.html       # Floor plan view
    ├── room101.html         # Live room dashboard
    ├── room102.html
    └── room103.html
```

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Train ML model (run once after collecting data)
python train_model.py

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL connection string |

## Why This Architecture?

Fixed thresholds fail across different locations — a kitchen runs hotter than a server room, Kolkata summers differ from hill station winters. FireFlux solves this by training a separate Isolation Forest model per room on that room's own historical data. The ML layer handles location and climate variance while IS 2189 provides the legally compliant danger threshold that never changes.

---

Built by Teesta Kar — 2nd year CSE
