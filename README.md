# 🔥 FireFlux — Real-Time IoT Fire Detection & Response System

**Real-time fire detection and response with machine learning and IoT sensors.**
ESP32 sensors → FastAPI backend → PostgreSQL → ML anomaly detection → WebSocket broadcast → browser dashboard.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/fastapi-0.110%2B-009688?style=flat-square)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/postgresql-15%2B-336791?style=flat-square)](https://postgresql.org)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.3%2B-F7931E?style=flat-square)](https://scikit-learn.org)
[![ESP32](https://img.shields.io/badge/esp32-arduino-red?style=flat-square)](https://espressif.com)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](#license)

> **Status:** Single-sensor prototype. Evaluated on synthetic anomalies only. Not tested against real fire events.

---

## Table of Contents

- [Overview](#overview)
- [Why This Architecture?](#why-this-architecture)
- [Tech Stack](#tech-stack)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [3-Layer Detection System](#3-layer-detection-system)
- [Repository Structure](#repository-structure)
- [Database Schema](#database-schema)
- [Risk Assessment Engine](#risk-assessment-engine)
- [Machine Learning Pipeline](#machine-learning-pipeline)
- [API Reference](#api-reference)
- [WebSocket Protocol](#websocket-protocol)
- [Hardware Setup](#hardware-setup)
- [Installation & Setup](#installation--setup)
- [Frontend](#frontend)
- [Data Flow](#data-flow)
- [Configuration Reference](#configuration-reference)
- [Testing & Validation](#testing--validation)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

FireFlux is a prototype fire-risk monitoring backend for a single room sensor. Fixed thresholds are a poor fit for every space: a kitchen runs hotter than a server room, and summer readings differ from winter ones. A single threshold can produce false alarms in one place and miss real risk in another.

FireFlux addresses this with three parts:

1. **Isolation Forest anomaly model.** Learns what normal temperature and gas readings look like for the monitored space and flags readings that don't fit that pattern.
2. **Fixed per-value safety limits.** Inspired by IS 2189. These always apply, so a single elevated value is never classed as safe, even if the model says normal.
3. **Hardware failsafe.** A buzzer on the ESP32 that sounds locally, independent of the network.

The model answers "is this unusual for this room?" The fixed limits answer "is this dangerous or elevated?" Fire-level danger is decided by the limits, not by the model.

**Evaluation:** On a time-ordered holdout with synthetic anomalies (5 random seeds), the anomaly model reaches ROC-AUC 0.98 and recall 0.90 on medium-difficulty deviations. It is weak on subtle deviations (ROC-AUC 0.69). There is no labeled fire data, so these numbers measure deviation detection, not fire detection.

---

## Why This Architecture?

### The Problem with Fixed Thresholds

- A reading that is normal in one room can be unusual in another.
- A threshold tuned for one room can miss problems in another, or trigger when someone opens a window.
- Readings also drift over time, so a model trained on old data gradually loses accuracy.

### The Approach: Learned Baseline + Fixed Limits

| Component | Question it answers | Guarantee |
|-----------|--------------------|-----------|
| **Isolation Forest** | Is this reading unusual for this room? | Adapts to the room's own history |
| **Fixed limits** | Is this reading dangerous or elevated? | Same rule every time, independent of the model |

A reading the model flags as anomalous is only raised to danger if it crosses a fixed limit. A reading the model flags but that stays in a physically normal range is downgraded to safe. A single elevated value is never classed as safe, whatever the model says.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Hardware** | ESP32 DevKit V1 | WiFi microcontroller + GPIO control |
| | DHT11 | Temperature sensor |
| | MQ2 | Gas/smoke sensor (units depend on calibration) |
| | HC-SR501 PIR | Motion detection (stored, not used by the model) |
| **Backend** | FastAPI | REST API + WebSocket server |
| | Python 3.10+ | Core runtime |
| **Database** | PostgreSQL | Persistent readings, assessments, alerts |
| | SQLAlchemy | ORM |
| **ML** | Scikit-learn | Isolation Forest model training |
| | joblib | Model serialization (`fire_model.pkl`) |
| **Real-time** | WebSockets (FastAPI) | Live browser updates |
| **Notifications** | Telegram Bot API | Push alerts on danger (5-minute cooldown per room) |
| **Frontend** | HTML5 / CSS3 / JS | Client-side pages |
| | Leaflet.js | Map view |
| | Chart.js | Sensor history graphs |
| **Deployment** | Docker | Containerization (see [Deployment](#deployment)) |

---

## Key Features

✅ **Real-time Sensor Ingestion**
ESP32 sends temperature, gas, and motion readings to `POST /ingest`.

✅ **ML Anomaly Detection**
Isolation Forest trained on historical temperature and gas readings. Flags readings that deviate from the learned pattern. Evaluated with a time-ordered holdout and synthetic anomalies.

✅ **Fixed Safety Limits**
Danger at temperature ≥ 78°C or gas ≥ 2000. Elevated readings (temperature > 45°C or gas > 1000) are never classed as safe, even if the model says normal.

✅ **Hardware Failsafe**
Onboard buzzer on the ESP32 triggers locally on danger, without requiring the network.

✅ **Telegram Alerts**
Notifications on danger with a 5-minute per-room cooldown. Includes room, reason, sensor values, and time.

✅ **Live Web Dashboard**
Browser pages subscribe to the WebSocket and update as readings arrive.

✅ **Simulator Panel**
Test the system without hardware by sending readings through Swagger or `POST /ingest`.

---

## System Architecture

```
                    ┌──────────────────────────────────────────────────────┐
                    │                  FireFlux System                     │
                    │                                                      │
  ┌──────────────┐  │  ┌────────────────────────────────────────────────┐  │
  │    ESP32     │  │  │              FastAPI :8000                     │  │
  │              │  │  │                                                │  │
  │  DHT11 ──┐   │  │  │  POST /ingest (from hardware and REST)         │  │
  │  MQ2  ──┼───┼──┼──►│         │                                      │  │
  │  PIR  ──┘   │  │  │         │                                      │  │
  │             │  │  │         ├─► assess_risk()                      │  │
  │  🔊Buzzer   │  │  │         │       ├─► Isolation Forest           │  │
  │  (offline)  │  │  │         │       ├─► fixed safety limits        │  │
  └─────────────┘  │  │         │       └─► risk_level + reason        │  │
                   │  │         │                                      │  │
  ┌─────────────┐  │  │         ├─► alert logic                        │  │
  │ Python Sim  │  │  │         │       └─► danger → alert row         │  │
  │(Rooms 2, 3) │──┼──►         │                                      │  │
  └─────────────┘  │  │         ├─► Telegram alert (5-min cooldown)    │  │
                   │  │         │                                      │  │
                   │  │         ├─► PostgreSQL                         │  │
                   │  │         │   ┌─────────────────────────────┐    │  │
                   │  │         └──►│ 4 tables:                   │    │  │
                   │  │             │ • rooms                     │    │  │
                   │  │             │ • readings                  │    │  │
                   │  │             │ • risk_assessments          │    │  │
                   │  │             │ • alerts                    │    │  │
                   │  │             └─────────────────────────────┘    │  │
                   │  │                                                │  │
                   │  └─────────────────┬──────────────────────────────┘  │
                   │                    │                                 │
                   │                    ▼                                 │
                   │  ┌────────────────────────────────────────────────┐  │
                   │  │   WebSocket Broadcast (ws://<host>:8000/ws)    │  │
                   │  │   Sent to all clients; clients filter by room  │  │
                   │  └─────────────────┬──────────────────────────────┘  │
                   │                    │                                 │
                   │                    ▼                                 │
                   │  ┌────────────────────────────────────────────────┐  │
                   │  │            Browser Clients                     │  │
                   │  │  ┌──────────────────────────────────────────┐  │  │
                   │  │  │  index.html (city dashboard)             │  │  │
                   │  │  │  • Leaflet.js map                        │  │  │
                   │  │  │  • Building status cards                 │  │  │
                   │  │  │  • Simulator panel (temp/gas)            │  │  │
                   │  │  └──────────────────────────────────────────┘  │  │
                   │  │  ┌──────────────────────────────────────────┐  │  │
                   │  │  │  buildingA.html (floor plan)             │  │  │
                   │  │  │  • Grid of room tiles (live status)      │  │  │
                   │  │  │  • Exit sign alerts (red on danger)      │  │  │
                   │  │  └──────────────────────────────────────────┘  │  │
                   │  │  ┌──────────────────────────────────────────┐  │  │
                   │  │  │  room10X.html (per-room dashboard)       │  │  │
                   │  │  │  • Sensor bars                           │  │  │
                   │  │  │  • Chart of recent readings              │  │  │
                   │  │  │  • Timeline table                        │  │  │
                   │  │  └──────────────────────────────────────────┘  │  │
                   │  └────────────────────────────────────────────────┘  │
                   └──────────────────────────────────────────────────────┘
```

---

## 3-Layer Detection System

FireFlux has three layers. The model and the fixed limits both run on the server. The buzzer runs on the ESP32 independently of the server.

### Layer 1: Hardware Failsafe (ESP32 Onboard)

**Goal:** A local alarm that does not depend on WiFi or the server.

```cpp
// Runs on the ESP32 (verify against firmware/esp32_sensor.ino)
if (temperature >= 78 || gas_value >= 2000) {
    digitalWrite(BUZZER_PIN, HIGH);
    // Buzzer behavior, such as repeat interval, is defined in the firmware
}
```

**Guarantees:**
- Works without internet access.
- Does not depend on the Python backend or the trained model.
- Its thresholds should match Layer 3 so the two layers agree.

---

### Layer 2: Isolation Forest Anomaly Detection (FastAPI + Scikit-learn)

**Goal:** Learn what normal looks like for the monitored sensor and flag readings that don't fit.

**Features:** `temperature` and `gas_value` only. Motion was removed from the model because it caused false warnings during testing.

**Training** (`train_model.py`):

```python
model = IsolationForest(contamination=0.02, n_estimators=100, random_state=42)
model.fit(df[["temperature", "gas_value"]])
joblib.dump(model, "fire_model.pkl")
```

**Inference** (`main.py`):

```python
X = pd.DataFrame([[temperature, gas_value]], columns=["temperature", "gas_value"])
is_anomaly = model.predict(X)[0] == -1
```

The decision uses the cutoff the model learned during training (`model.offset_`), not a hardcoded number.

**Advantages:**
- Learns a baseline from the room's own history.
- Needs no labeled data to train.
- Simple to explain and to evaluate.

**Limitations:**
- Learns a single baseline for the one sensor it was trained on.
- The baseline is frozen at training time. Retrain as new data arrives.
- Subtle deviations (for example, a 2–3°C shift) are mostly missed.

---

### Layer 3: Fixed Safety Limits (FastAPI)

**Goal:** Guarantee that dangerous or elevated readings are never classed as safe, regardless of the model.

**Limits in use** (inspired by IS 2189; design values, not a certified compliance implementation):

```
Danger:    temperature ≥ 78°C   OR  gas ≥ 2000
Elevated:  temperature > 45°C   OR  gas > 1000
Safe:      model says normal AND no value elevated
```

**Advantages:**
- Same rule every time, independent of model training.
- Easy to read, explain, and change.
- Works even if the model file is missing.

**Note:** Gas units depend on MQ2 calibration. The 2000 and 1000 limits are in the sensor's current units and need recalibration against a known reference before they mean ppm.

---

## Repository Structure

```
fireflux/
├── README.md                    # This file
├── Backend/
│   ├── main.py                  # FastAPI app, routes, WebSocket manager, risk engine
│   ├── train_model.py           # Loads readings, fits Isolation Forest, saves fire_model.pkl
│   ├── evaluate_model.py        # Time-ordered evaluation with synthetic anomalies
│   ├── fire_model.pkl           # Trained model (generated, not committed)
│   ├── .env                     # Local secrets (not committed)
│   ├── ingestion/
│   │   ├── database.py          # SQLAlchemy engine, SessionLocal
│   │   ├── database_models.py   # ORM tables (Room, Reading, RiskAssessment, Alert)
│   │   └── models.py            # Pydantic input schema
│   ├── Dockerfile               # Only if you have built it (see Deployment)
│   └── requirements.txt         # Only if you have generated it with pip freeze
│
├── firmware/
│   └── esp32_sensor.ino         # Arduino sketch for ESP32
│
└── frontend/                    # Browser dashboard pages
```

---

## Database Schema

Tables are created automatically on startup by `Base.metadata.create_all(bind=engine)`. The column definitions live in `ingestion/database_models.py`, which is the source of truth. The summary below matches what `main.py` reads and writes.

### `rooms`

| Column | Purpose |
|--------|---------|
| `id` | Room identifier (primary key) |
| `name` | Display name |
| `floor` | Floor number |
| `exits` | Exit information shown on alerts |

### `readings`

One row per sensor reading.

| Column | Purpose |
|--------|---------|
| `id` | Primary key |
| `room_id` | Room the reading came from |
| `temperature` | Degrees Celsius |
| `gas_value` | Gas reading (units depend on calibration) |
| `motion` | Motion flag from PIR |
| `timestamp` | When the reading was stored |

### `risk_assessments`

One row per reading, written right after it.

| Column | Purpose |
|--------|---------|
| `id` | Primary key |
| `reading_id` | The reading this assessment belongs to |
| `room_id` | Room ID |
| `risk_score` | Score (see [Risk Assessment Engine](#risk-assessment-engine)) |
| `risk_level` | `safe`, `warning`, or `danger` |
| `reason` | Human-readable explanation |

### `alerts`

One row per danger event that triggered an alert.

| Column | Purpose |
|--------|---------|
| `id` | Primary key |
| `room_id` | Room ID |
| `risk_assessment_id` | The assessment that triggered the alert |
| `message` | Alert text |
| `unsafe_exits` | Exit information from the room |
| `notified` | Whether the Telegram message was sent |
| `created_at` | When the alert was created |

**Deleting data:** `alerts` and `risk_assessments` reference `readings`. Delete child rows first, or PostgreSQL will refuse the delete.

---

## Risk Assessment Engine

### `assess_risk()` (main.py)

Returns `risk_level` (`safe`, `warning`, or `danger`), `risk_score`, and `reason`.

**Room 1 (model + limits):**

1. If `fire_model.pkl` is not loaded, use the danger limits only.
2. Ask the model whether the reading is anomalous.
3. If the reading is normal **and** no value is elevated → `safe`.
4. If a danger limit is crossed → `danger`.
5. If the model flagged it, but temperature ≤ 45 and gas ≤ 1000 → `safe` (mild model flag in a physically normal range).
6. Otherwise → `warning`.

**Rooms 2 and 3 (no model):** `danger` if gas ≥ 2000 or temperature ≥ 78; otherwise `safe`.

### Decision Tree (Room 1)

```
Input: temperature, gas_value

┌─ Model not loaded?
│  ├─ YES → danger if gas ≥ 2000 or temp ≥ 78, else safe
│  └─ NO  → continue
│
├─ Model says normal AND no value elevated?
│  ├─ YES → SAFE
│  └─ NO  → continue
│
├─ Gas ≥ 2000 or temp ≥ 78?
│  ├─ YES → DANGER
│  └─ NO  → continue
│
├─ Temp ≤ 45 AND gas ≤ 1000?
│  ├─ YES → SAFE (mild model flag)
│  └─ NO  → continue
│
└─ WARNING
```

### Risk Score

`risk_score` is not a calibrated probability.
- For model-driven results, it is the absolute value of the model's decision score, rounded.
- For danger from the fixed limits, it is 0.9.
- For safe, it is 0.0.

---

## Machine Learning Pipeline

### Training

```powershell
python train_model.py
```

This loads all rows from `readings`, fits one Isolation Forest on `temperature` and `gas_value`, and saves `fire_model.pkl` in `Backend/`. Restart the server afterwards so it loads the new file.

**Data cleaning before training:** Rows with temperature ≥ 45 or gas ≥ 1000 were removed from `readings` before the final training. These were test inserts and out-of-range values. Leaving them in taught the model that high readings were normal, so it labeled a 31°C / 1359 gas reading as safe.

### Model Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `n_estimators` | 100 | Standard default, stable results |
| `contamination` | 0.02 | Expects about 2% of training data to look unusual |
| `random_state` | 42 | Reproducible training |
| Features | `temperature`, `gas_value` | Motion caused false warnings |

### Drift and Retraining

The baseline is fixed when the model is trained. If the room changes (sensor placement, usage, season), the false-alarm rate rises. Retrain on recent normal data to keep the baseline current.

### Data Variety

A single sensor produces readings that cluster tightly, so more rows from the same room add little new information. Time coverage (different times of day, usage patterns, and seasons) matters more than row count.

### Evaluation

Evaluation is in `evaluate_model.py`:

```powershell
python evaluate_model.py
```

**Method**

- **Split:** time-ordered. The oldest 80% of rows train the model. The newest 20% form the normal test set. The test set is never seen during training.
- **Synthetic anomalies** (300 per difficulty band), generated from the test data:
  - *Easy:* temperature 50–100°C, gas 1500–3000. Far outside any normal reading.
  - *Medium:* both features shifted by 3–5 robust standard deviations from real normal readings.
  - *Hard:* one feature shifted by 1.5–2.5 robust standard deviations.
- **Robust spread:** median absolute deviation (MAD), so outliers don't inflate the spread.
- **Repeats:** 5 random seeds, reported as mean ± standard deviation.

**Results** (medium-difficulty synthetic anomalies, 5 seeds, cleaned data: about 2,221 training rows and 556 test rows)

| Metric | Value | What it means |
|--------|-------|---------------|
| ROC-AUC | 0.978 ± 0.008 | Chance a random anomaly scores higher than a random normal reading |
| PR-AUC | 0.957 ± 0.016 | Precision–recall area; informative when anomalies are rare |
| Recall | 0.905 ± 0.030 | Share of anomalies caught |
| Precision | 0.896 ± 0.015 | Share of flagged readings that were anomalies |
| F1 | 0.900 ± 0.015 | Balance of precision and recall |
| False-positive rate | 0.057 ± 0.010 | Share of normal test readings flagged (optimistic; see below) |

**Hard-difficulty anomalies:** ROC-AUC 0.693 ± 0.010, recall 0.222 ± 0.015. The model misses most subtle deviations.

**Easy-difficulty anomalies:** ROC-AUC 1.000, recall 1.000. Expected, but says little about real performance.

**Interpretation**

- **No labeled fire data exists.** These numbers measure deviation from the room's learned baseline, not fire detection.
- **The false-positive rate is optimistic.** The cleanup removed every row with temperature ≥ 45 or gas ≥ 1000, so the normal test rows are all low readings. Real false-alarm rates are likely higher.
- **Accuracy is not reported.** Most readings are normal, so a weak model can still score high accuracy.
- **Results depend on one sensor's history.** They would change with different data.

---

## API Reference

**Base URL:** `http://<host>:8000`
**Interactive docs:** `http://<host>:8000/docs`

### `POST /ingest`

Saves a reading, runs the risk assessment, stores the result, sends an alert on danger, and broadcasts to WebSocket clients.

**Request:**
```json
{
  "room_id": 1,
  "temperature": 28.0,
  "gas_value": 400.0,
  "motion": false
}
```

**Response:**
```json
{
  "status": "saved",
  "reading_id": 2860,
  "risk_score": 0.12,
  "risk_level": "danger",
  "reason": "Gas critically high, Temperature critically high"
}
```

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"room_id": 1, "temperature": 28.0, "gas_value": 400.0, "motion": false}'
```

### `GET /rooms`

Lists all rooms with `id`, `name`, `floor`, and `exits`.

### `GET /rooms/{room_id}/latest`

The latest reading for a room with its risk level and reason. Returns 404 if the room has no data.

```json
{
  "room_id": 1,
  "temperature": 28.0,
  "gas_value": 400.0,
  "motion": false,
  "timestamp": "2026-03-10T20:42:15.123456",
  "risk_score": 0.0,
  "risk_level": "safe",
  "reason": "All readings normal"
}
```

### `GET /rooms/{room_id}/history?limit=50`

Recent readings for a room with their risk levels, newest first. Each item has `id`, `temperature`, `gas_value`, `motion`, `timestamp`, `risk_level`, `risk_score`, and `reason`.

### `GET /alerts`

Alerts that have not yet been marked as notified. Fields: `id`, `room_id`, `message`, `unsafe_exits`, `created_at`.

---

## WebSocket Protocol

**Endpoint:** `ws://<host>:8000/ws/{room_id}`

After each `/ingest` call, the server sends a JSON message to connected clients:

```json
{
  "room_id": 1,
  "temperature": 28.0,
  "gas_value": 400.0,
  "motion": false,
  "risk_score": 0.0,
  "risk_level": "safe",
  "reason": "All readings normal"
}
```

**Current behavior:** the server sends every message to all connected clients, regardless of the `/ws/{room_id}` path they connected to. Clients should check `room_id` themselves. Per-room filtering is on the roadmap.

---

## Hardware Setup

> **Verify before relying on this section.** The pin mapping, buzzer behavior, and firmware snippets below were written before the firmware was checked. Confirm each one against `firmware/esp32_sensor.ino`.

### Components

| Component | Model | Role |
|-----------|-------|------|
| MCU | ESP32 DevKit V1 | WiFi, GPIO, onboard buzzer |
| Temperature | DHT11 | Room temperature |
| Gas / smoke | MQ2 | Gas reading (needs calibration to convert to ppm) |
| Motion | HC-SR501 PIR | Motion flag |

### Pin Mapping

| GPIO | Sensor | Type | Notes |
|------|--------|------|-------|
| 4 | DHT11 DATA | Digital | 10 kΩ pull-up to 3.3 V |
| 34 | MQ2 AOUT | Analog input | ADC1; GPIO 34–39 are input-only |
| 27 | PIR OUT | Digital input | HIGH when motion detected |
| 2 | Buzzer | Digital output | Active buzzer |

Verify the wiring before powering the board.

### Firmware Configuration

Edit `firmware/esp32_sensor.ino` before uploading:

```cpp
const char* ssid      = "YOUR_WIFI_SSID";
const char* password  = "YOUR_WIFI_PASSWORD";
const char* serverUrl = "http://<YOUR_PC_IP>:8000/ingest";

#define DHT_PIN     4
#define MQ2_PIN     34
#define PIR_PIN     27
#define BUZZER_PIN  2
#define ROOM_ID     1
```

Set `serverUrl` to the backend's `/ingest` endpoint on your machine's LAN IP. `/ingest` is the only sensor endpoint in `main.py`.

### Sensor Warm-up

The MQ2 needs a warm-up period after power-on before its readings are stable. Allow it to warm up before collecting training data, and discard early readings.

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- PostgreSQL 15+ (local install)
- Arduino IDE 2.x with ESP32 board support (for firmware)

### Step 1: Clone the repository

```bash
git clone https://github.com/<your-username>/fireflux.git
cd fireflux
```

### Step 2: Create the virtual environment

```powershell
cd Backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

```powershell
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv httpx joblib scikit-learn pandas numpy
```

Once everything runs, record the exact versions with `pip freeze > requirements.txt`.

### Step 4: Create the database

```sql
CREATE DATABASE fireflux;
```

### Step 5: Configure environment variables

Create `Backend/.env`:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/fireflux
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

The app raises an error on startup if `TELEGRAM_TOKEN` or `TELEGRAM_CHAT_ID` is missing.

**Telegram setup:**
1. Message `@BotFather` on Telegram and send `/newbot`.
2. Copy the token it gives you.
3. Send a message to your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat ID.

Never commit `.env` or a database password to Git.

### Step 6: Train the model

```powershell
python train_model.py
```

Without `fire_model.pkl`, the app still runs and uses only the fixed danger limits for Room 1.

### Step 7: Start the backend

```powershell
uvicorn main:app --reload
```

Look for `ML model loaded successfully` in the output. If you see the warning instead, the model file is missing. Run `train_model.py` first.

Open `http://127.0.0.1:8000/docs` to test endpoints.

### Step 8: Flash the ESP32 (optional)

1. Open Arduino IDE 2.x and install the ESP32 board package.
2. Install the libraries: `ArduinoJson`, `DHT sensor library` (Adafruit), `Adafruit Unified Sensor` (Adafruit).
3. Open `firmware/esp32_sensor.ino` and set the WiFi credentials, `serverUrl`, and `ROOM_ID`.
4. Select **Tools → Board → ESP32 Dev Module** and the correct port.
5. Upload, then open the Serial Monitor at 115200 baud to confirm readings are being sent.

### Firewall (Windows, optional for ESP32 access)

Allow port 8000 so the ESP32 can reach the backend on your LAN:

```powershell
# Run PowerShell as Administrator
New-NetFirewallRule `
  -DisplayName "FireFlux API (Port 8000)" `
  -Direction   Inbound `
  -Protocol    TCP `
  -LocalPort   8000 `
  -Action      Allow
```

---

## Frontend

The frontend pages are static HTML files that connect to the backend's REST endpoints and WebSocket. Open them directly in a browser, or serve the folder with any static file server.

Update the API and WebSocket URLs at the top of each page's script to point at your backend:

```javascript
const API = "http://127.0.0.1:8000";
const WS  = "ws://127.0.0.1:8000";
```

**Typical behavior:**
- Pages load the latest reading with `GET /rooms/{id}/latest`.
- They subscribe to `/ws/{room_id}` for updates.
- Colour is set from `risk_level` (`safe`, `warning`, `danger`).
- Pages should filter messages by `room_id`, because the backend currently broadcasts to all clients.

### `index.html` — City Dashboard

- Leaflet.js map with markers per building
- Sidebar status cards per room
- Simulator panel (temperature, gas, motion) that sends to `POST /ingest`

### `buildingA.html` — Floor Plan View

- Room tiles coloured by `risk_level`
- Loads `GET /rooms/{id}/latest` on open, then updates from WebSocket

### `room10X.html` — Per-Room Dashboard

- Sensor bars for temperature and gas
- Colour changes at the fixed limits: 45°C and 1000 for elevated, 78°C and 2000 for danger
- Chart.js graph of recent readings from `GET /rooms/{id}/history`
- Timeline table of recent readings

---

## Data Flow

```
1.  ESP32 reads temperature (DHT11), gas (MQ2), and motion (PIR)
2.  Buzzer check on the ESP32 (local, independent of network)
3.  POST /ingest  {room_id, temperature, gas_value, motion}
4.  FastAPI saves the reading                     → readings
5.  assess_risk()
      ├─ Isolation Forest decision (Room 1)
      └─ fixed limits (danger / elevated)
6.  Save the assessment                           → risk_assessments
7.  If danger: create alert row                   → alerts
8.  If danger: Telegram message (5-minute cooldown per room)
9.  Broadcast the result to WebSocket clients
10. Browser updates the status display
```

---

## Configuration Reference

| Variable | Location | Description |
|----------|----------|-------------|
| `DATABASE_URL` | `Backend/.env` | PostgreSQL connection string |
| `TELEGRAM_TOKEN` | `Backend/.env` | Telegram bot token (required by the app) |
| `TELEGRAM_CHAT_ID` | `Backend/.env` | Telegram chat ID for alerts (required by the app) |
| `ssid` / `password` | `esp32_sensor.ino` | WiFi credentials |
| `serverUrl` | `esp32_sensor.ino` | Backend `/ingest` URL (LAN IP and port) |
| `ROOM_ID` | `esp32_sensor.ino` | Room identifier sent with each reading |
| `DHT_PIN`, `MQ2_PIN`, `PIR_PIN`, `BUZZER_PIN` | `esp32_sensor.ino` | GPIO assignments |
| `API`, `WS` | `frontend/*.html` | Backend REST and WebSocket base URLs |

Thresholds are set in `main.py` (`assess_risk()`), not in `.env`. Changing a threshold there changes the app's behavior, so update the evaluation and this README too.

---

## Testing & Validation

### Swagger (recommended)

Open `http://127.0.0.1:8000/docs`, choose `POST /ingest`, click **Try it out**, and send these inputs:

| temperature | gas_value | Expected `risk_level` |
|-------------|-----------|-----------------------|
| 29.0 | 400.0 | `safe` |
| 31.0 | 1359.0 | `warning` |
| 65.0 | 513.0 | `warning` |
| 90.0 | 2500.0 | `danger` |

Each request writes a row to `readings`. Test rows that remain in the table become training data, so delete them and retrain before relying on the model.

### curl examples

```bash
# Safe reading
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"room_id": 1, "temperature": 29.0, "gas_value": 400.0, "motion": false}'

# Warning (elevated gas)
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"room_id": 1, "temperature": 31.0, "gas_value": 1359.0, "motion": false}'

# Danger (high temperature and gas)
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"room_id": 1, "temperature": 90.0, "gas_value": 2500.0, "motion": true}'
```

### Model evaluation

```powershell
python evaluate_model.py
```

See [Evaluation](#evaluation) for what the output means.

### Checking stored data

```sql
SELECT COUNT(*) AS total FROM readings;

SELECT COUNT(*) FILTER (WHERE temperature >= 45 OR gas_value >= 1000) AS elevated
FROM readings;
```

---

## Deployment

### Docker (only if you have built and run it)

```bash
cd Backend
docker build -t fireflux:latest .
docker run -p 8000:8000 --env-file .env fireflux:latest
```

Keep this section only if the `Dockerfile` exists and you have run this command successfully.

### Cloud hosting (planned)

Render (backend) and Supabase (PostgreSQL) are options for hosting. Neither is set up yet. When you deploy, set `DATABASE_URL`, `TELEGRAM_TOKEN`, and `TELEGRAM_CHAT_ID` as environment variables, and use `wss://` for the WebSocket on HTTPS.

### Notes for production

- Retrain on a rolling window of recent normal data.
- Add authentication to write endpoints before exposing the server beyond your LAN.
- Restrict CORS (`allow_origins=["*"]` is for development only).

---

## Roadmap

- [x] Isolation Forest anomaly model with time-ordered evaluation
- [x] Fixed safety limits that override "safe"
- [x] Telegram alerts with per-room cooldown
- [x] Live WebSocket broadcast
- [ ] Event lifecycle tracking (danger events with open and close times)
- [ ] Filter WebSocket broadcast by room
- [ ] Scheduled retraining on a rolling window
- [ ] Added features (for example, rate of change) to improve subtle-anomaly detection
- [ ] Per-room models or features for multiple sensors
- [ ] Calibrated gas units (ppm)
- [ ] Evaluation on labeled real data
- [ ] Authentication on API routes
- [ ] Docker and cloud deployment (verified)
- [ ] Mobile-responsive frontend

---

## License

MIT License

Copyright (c) 2026 FireFlux Project

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## Questions & Support

For questions about this project:
- 📧 Open an issue on GitHub
- 💬 Check Swagger UI at `/docs` for API details

---
