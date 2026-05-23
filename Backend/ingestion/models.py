from pydantic import BaseModel

class SensorReadingInput(BaseModel):
    room_id: int
    temperature: float
    gas_value: float
    motion: bool