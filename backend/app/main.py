import json
import re
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import Base, engine, SessionLocal

from app.models.employee import Employee
from app.models.submission import Submission
from app.models.receipt import Receipt
from app.models.verdict import Verdict
from app.models.override import Override

from app.services.policy_service import build_policy_index, search_policies
from app.services.receipt_service import extract_receipt_text, parse_receipt_with_llm
from app.services.adjudication_service import adjudicate_receipt
from app.services.policy_qa_service import answer_policy_question


app = FastAPI(title="Northwind AI Expense Review")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


class AdjudicationRequest(BaseModel):
    receipt: dict
    employee: Optional[dict] = None
    submission: Optional[dict] = None


class OverrideRequest(BaseModel):
    verdict_id: int
    reviewer: str
    new_status: str
    reason: str


class PolicyQuestionRequest(BaseModel):
    question: str


def parse_trip_dates(trip_dates: str):
    if not trip_dates:
        return None, None

    parts = re.split(r"\s+to\s+", trip_dates.strip())

    if len(parts) == 2:
        return parts[0], parts[1]

    return trip_dates, None


def seed_from_employee_json():
    db: Session = SessionLocal()

    base_dir = Path(__file__).resolve().parent.parent.parent
    submissions_dir = base_dir / "data" / "submissions"

    if not submissions_dir.exists():
        db.close()
        return

    for employee_file in submissions_dir.glob("*/employee_info.json"):
        data = json.loads(employee_file.read_text(encoding="utf-8"))

        employee = db.query(Employee).filter(
            Employee.employee_id == data.get("employee_id")
        ).first()

        if not employee:
            employee = Employee(
                employee_id=data.get("employee_id"),
                name=data.get("name"),
                grade=data.get("grade"),
                title=data.get("title"),
                department=data.get("department"),
                manager_id=data.get("manager_id"),
                home_base=data.get("home_base"),
            )
            db.add(employee)

        trip_start, trip_end = parse_trip_dates(data.get("trip_dates"))

        existing_submission = db.query(Submission).filter(
            Submission.employee_id == data.get("employee_id"),
            Submission.trip_start_date == trip_start,
            Submission.trip_end_date == trip_end,
        ).first()

        if not existing_submission:
            submission = Submission(
                employee_id=data.get("employee_id"),
                trip_purpose=data.get("trip_purpose"),
                trip_start_date=trip_start,
                trip_end_date=trip_end,
                status="seeded",
            )
            db.add(submission)

    db.commit()
    db.close()


@app.on_event("startup")
def startup_event():
    seed_from_employee_json()


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Northwind AI Expense Review API running"
    }


@app.post("/seed")
def seed_employees():
    seed_from_employee_json()
    return {"message": "Employees seeded from sample submissions"}


@app.get("/employees")
def get_employees():
    db: Session = SessionLocal()
    employees = db.query(Employee).all()
    db.close()
    return employees


@app.get("/submissions")
def get_submissions():
    db: Session = SessionLocal()
    submissions = db.query(Submission).all()
    db.close()
    return submissions


@app.post("/policies/index")
def index_policies():
    return build_policy_index()


@app.get("/policies/search")
def policy_search(q: str):
    return search_policies(q)


@app.post("/policies/ask")
def ask_policy(request: PolicyQuestionRequest):
    return answer_policy_question(request.question)


@app.post("/receipts/extract")
def extract_receipt(file: UploadFile = File(...)):
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)

    file_path = upload_dir / file.filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    raw_text = extract_receipt_text(str(file_path))
    parsed = parse_receipt_with_llm(raw_text, str(file_path))

    db: Session = SessionLocal()

    receipt = Receipt(
        filename=file.filename,
        merchant=parsed.get("merchant"),
        date=parsed.get("date"),
        amount=parsed.get("amount"),
        category=parsed.get("category"),
        location=parsed.get("location"),
        has_alcohol=parsed.get("has_alcohol", False),
        raw_text=raw_text,
        parsed_json=json.dumps(parsed)
    )

    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    db.close()

    return {
        "receipt_id": receipt.id,
        "filename": file.filename,
        "raw_text": raw_text,
        "parsed": parsed
    }


@app.post("/adjudicate")
async def adjudicate(request: AdjudicationRequest):
    verdict = adjudicate_receipt(
        receipt=request.receipt,
        employee=request.employee,
        submission=request.submission
    )

    db: Session = SessionLocal()

    verdict_row = Verdict(
        receipt_id=request.receipt.get("id"),
        status=verdict.get("status"),
        reasoning=verdict.get("reasoning"),
        confidence=verdict.get("confidence"),
        violations_json=json.dumps(verdict.get("violations", [])),
        citations_json=json.dumps(verdict.get("citations", []))
    )

    db.add(verdict_row)
    db.commit()
    db.refresh(verdict_row)
    db.close()

    verdict["verdict_id"] = verdict_row.id

    return verdict


@app.post("/override")
def override_verdict(request: OverrideRequest):
    db: Session = SessionLocal()

    verdict = db.query(Verdict).filter(
        Verdict.id == request.verdict_id
    ).first()

    if not verdict:
        db.close()
        return {"error": "Verdict not found"}

    override = Override(
        verdict_id=verdict.id,
        reviewer=request.reviewer,
        original_status=verdict.status,
        new_status=request.new_status,
        reason=request.reason
    )

    verdict.status = request.new_status

    db.add(override)
    db.commit()
    db.refresh(override)
    db.close()

    return {
        "message": "Override saved",
        "override_id": override.id,
        "updated_status": request.new_status
    }


@app.get("/receipts")
def get_receipts():
    db: Session = SessionLocal()
    receipts = db.query(Receipt).all()
    db.close()
    return receipts


@app.get("/verdicts")
def get_verdicts():
    db: Session = SessionLocal()
    verdicts = db.query(Verdict).all()
    db.close()
    return verdicts


@app.get("/overrides")
def get_overrides():
    db: Session = SessionLocal()
    overrides = db.query(Override).all()
    db.close()
    return overrides