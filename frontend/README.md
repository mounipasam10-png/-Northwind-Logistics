# Northwind AI Expense Review

AI-powered expense review system for automated receipt extraction, policy-aware adjudication, human override workflows, and policy Q&A.

---

# Overview

Northwind AI Expense Review is an end-to-end AI expense compliance platform designed to automate employee expense review workflows.

The system allows users to:

- Upload receipts
- Extract structured expense data using LLMs
- Run automated policy adjudication
- Detect policy violations
- Apply human overrides
- Ask questions against a company policy library

The application demonstrates production-style AI workflow orchestration using FastAPI, React, OpenAI APIs, vector search, and policy reasoning.

---

# Features

## Receipt Extraction

- Upload receipt images or PDFs
- Extract:
  - merchant
  - amount
  - category
  - location
  - card details
  - line items
- Uses OpenAI-powered structured extraction

---

## Automated Adjudication

AI agent evaluates receipts against company policies.

Checks include:

- Alcohol restrictions
- Expense category rules
- Travel compliance
- Spending thresholds
- Class-of-service validation

Returns:

- APPROVED
- DENIED
- NEEDS_REVIEW

with confidence score and explanation.

---

## Human Override Workflow

Managers can override AI decisions with justification.

Tracks:

- override reason
- original verdict
- override timestamp

---

## Policy Q&A

Users can ask natural language questions such as:

Can alcohol be reimbursed during solo travel?

Uses semantic policy search + LLM reasoning.

---

## History Tracking

Stores:

- extracted receipts
- adjudication results
- override history

using SQLite persistence.

---

# Architecture

Frontend (React + Vite)
        |
        v
Backend API (FastAPI)
        |
        +-------------------+
        |                   |
        v                   v
OpenAI APIs           SQLite Database
        |
        v
Policy Search + Adjudication Engine

---

# Tech Stack

## Frontend

- React
- Vite
- Axios
- CSS

---

## Backend

- FastAPI
- Python 3
- SQLAlchemy
- Uvicorn

---

## AI / LLM

- OpenAI GPT models
- Prompt engineering
- Structured JSON extraction
- Policy reasoning

---

## Storage

- SQLite
- Local file uploads

---

## Deployment

- Render (Backend)
- Render Static Site (Frontend)
- GitHub

---

# Project Structure

backend/
│
├── app/
│   ├── core/
│   ├── models/
│   ├── services/
│   └── main.py
│
├── uploads/
├── storage/
├── .env
└── requirements.txt

frontend/
│
├── src/
├── public/
├── package.json
└── vite.config.js

---

# Setup

## 1. Clone Repository

```bash
git clone https://github.com/mounipasam10-png/-Northwind-Logistics.git
cd -Northwind-Logistics
```

---

## 2. Backend Setup

```bash
cd backend

python -m venv venv

venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 3. Configure Environment Variables

Create `.env`

```env
OPENAI_API_KEY=your_api_key
```

---

## 4. Run Backend

```bash
uvicorn app.main:app --reload
```

Backend runs on:

```text
http://localhost:8000
```

Swagger docs:

```text
http://localhost:8000/docs
```

---

## 5. Frontend Setup

```bash
cd frontend
npm install
```

Create `.env`

```env
VITE_API_URL=http://localhost:8000
```

Run frontend:

```bash
npm run dev
```

Frontend runs on:

```text
http://localhost:5173
```

---

# Deployment

## Backend Deployment (Render)

Backend deployed using Render Web Service.

Production URL:

```text
https://northwind-backend-cw56.onrender.com
```

API Docs:

```text
https://northwind-backend-cw56.onrender.com/docs
```

---

## Frontend Deployment (Render Static Site)

Frontend deployed using Render Static Site.

Production URL:

```text
https://northwind-frontend-dvn5.onrender.com
```

---

# API Endpoints

## Health Check

```http
GET /
```

## Employees

```http
GET /employees
```

## Receipt Extraction

```http
POST /receipts/extract
```

## Adjudication

```http
POST /adjudicate
```

## Policy Search

```http
GET /policies/search
```

## Policy Q&A

```http
POST /policies/ask
```

## Human Override

```http
POST /override
```
