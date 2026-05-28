from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from datetime import datetime
from app.core.database import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    merchant = Column(String, nullable=True)
    date = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    has_alcohol = Column(Boolean, default=False)
    raw_text = Column(Text, nullable=True)
    parsed_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)