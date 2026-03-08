from sqlalchemy import Column, Integer, Float, Boolean, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from ingestion.database import Base
from datetime import datetime


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))        # "Room 101"
    floor = Column(Integer)           # 1, 2, 3...
    exits = Column(JSONB)             # ["North Exit", "Stairwell B"]


class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    temperature = Column(Float)
    gas_value = Column(Float)
    motion = Column(Boolean)
    timestamp = Column(DateTime, default=datetime.utcnow)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reading_id = Column(Integer, ForeignKey("readings.id"))
    room_id = Column(Integer, ForeignKey("rooms.id"))
    risk_score = Column(Float)        # 0.0 to 1.0
    risk_level = Column(String(10))   # "safe" / "warning" / "danger"
    reason = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    risk_assessment_id = Column(Integer, ForeignKey("risk_assessments.id"))
    message = Column(Text)
    unsafe_exits = Column(JSONB)      # exits near the danger room
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)