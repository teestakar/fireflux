from fastapi import FastAPI

app = FastAPI()

# temporary storage (we'll replace with DB later)
users = {}

@app.get("/")
def home():
    return {"message": "Auth API running"}

@app.post("/register")
def register(username: str, password: str):
    if username in users:
        return {"error": "User already exists"}

    users[username] = password
    return {"message": "User registered successfully"}