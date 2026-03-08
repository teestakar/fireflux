import time
import requests
import random

SERVER_URL = "http://localhost:8000/ingest"

while True:
    for room_id in [2, 3]:
        requests.post(SERVER_URL, json={
            "room_id": room_id,
            "temperature": round(random.uniform(24.0, 35.0), 1),
            "gas_value": round(random.uniform(150.0, 600.0), 1),
            "motion": random.choice([True, False])
        })
    time.sleep(10)