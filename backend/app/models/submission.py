from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.core.database import Base

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, nullable=False)
    trip_purpose = Column(String, nullable=True)
    trip_start_date = Column(String, nullable=True)
    trip_end_date = Column(String, nullable=True)
    status = Column(String, default="seeded")
    created_at = Column(DateTime, default=datetime.utcnow)