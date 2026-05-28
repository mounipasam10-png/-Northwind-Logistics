from sqlalchemy import Column, Integer, String
from app.core.database import Base

class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    grade = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    department = Column(String, nullable=True)
    manager_id = Column(String, nullable=True)
    home_base = Column(String, nullable=True)