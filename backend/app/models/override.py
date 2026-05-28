from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.core.database import Base


class Override(Base):
    __tablename__ = "overrides"

    id = Column(Integer, primary_key=True, index=True)
    verdict_id = Column(Integer, nullable=False)
    reviewer = Column(String, nullable=False)
    original_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)