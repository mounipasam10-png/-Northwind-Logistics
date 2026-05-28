from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from app.core.database import Base


class Verdict(Base):
    __tablename__ = "verdicts"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, nullable=True)
    status = Column(String, nullable=False)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    violations_json = Column(Text, nullable=True)
    citations_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)