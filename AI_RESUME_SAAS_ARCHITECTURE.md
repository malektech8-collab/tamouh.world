AI Resume SaaS – Scalable Architecture & Development Guide
Version: 1.0
Goal: Long-term scalable, cost-effective, high-quality AI Resume Platform
1. Product Philosophy

This system is NOT:

A single LLM prompt

An automation script

A formatting wrapper

This system IS:

A deterministic AI pipeline

Structured resume engine

LLM-assisted reasoning layer

Template-based rendering engine

Monetizable SaaS infrastructure

2. High-Level Architecture
Frontend (Next.js / Vercel)
        ↓
FastAPI Backend (Auth + Job Creation)
        ↓
Redis Queue
        ↓
AI Worker (Python)
        ↓
LLM Provider (OpenAI)
        ↓
Validation Layer (Pydantic)
        ↓
Template Renderer (Jinja2 / docxtpl)
        ↓
PDF / DOCX Generation
        ↓
Object Storage (S3 / R2 / B2)
        ↓
Email Delivery
3. Technology Stack
Frontend

Next.js

Vercel

Stripe Checkout

Auth (Supabase or JWT)

Backend

FastAPI

Uvicorn

Pydantic

SQLAlchemy

PostgreSQL

Redis

Celery (or RQ)

AI Layer

OpenAI GPT-4o-mini (default)

GPT-4o (premium tier)

Strict JSON schema enforcement

Rendering

Jinja2 (HTML templates)

WeasyPrint (PDF)

docxtpl (DOCX)

Pandoc (optional alternative)

Storage

Cloudflare R2 (recommended)

Backblaze B2

AWS S3

Email

Resend

SendGrid

Billing

Stripe

4. Core Data Contract (Resume JSON)

All LLM outputs must conform to this structure.

ResumeDoc Schema
{
  "meta": {
    "language": "en",
    "target_role": "",
    "design": "classic",
    "ats_level": "strict"
  },
  "profile": {
    "full_name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "portfolio": ""
  },
  "headline": "",
  "summary": "",
  "skills": {
    "core": [],
    "tools": [],
    "domain": []
  },
  "experience": [
    {
      "company": "",
      "title": "",
      "location": "",
      "start": "",
      "end": "",
      "bullets": []
    }
  ],
  "education": [
    {
      "institution": "",
      "degree": "",
      "field": "",
      "start": "",
      "end": "",
      "details": []
    }
  ],
  "certifications": [],
  "projects": [],
  "languages": [],
  "achievements": [],
  "keywords": {
    "included": [],
    "missing": []
  }
}

This is your canonical resume object.

5. AI Worker Pipeline
Step 1: Extract

PDF → pdfplumber

DOCX → python-docx

Image → Tesseract OCR

Return cleaned text.

Step 2: Parse to ResumeDoc

LLM Prompt:

Convert raw resume text to structured ResumeDoc JSON

Strict schema enforcement

additionalProperties = false

Validate with Pydantic.

Retry if invalid.

Step 3: Resume Audit

LLM returns:

{
  "strengths": [],
  "weaknesses": [],
  "missing_sections": [],
  "ats_problems": [],
  "improvement_actions": [],
  "overall_score": 0
}
Step 4: Optimization

Input:

ResumeDoc

Audit JSON

Target Role

Output:

Updated ResumeDoc

Rules:

Only improve content

Never invent experience

Strengthen bullet clarity

Add quantification

Step 5: Validation Layer

Python validators check:

At least 3 bullets per job

Dates formatted correctly

Summary exists

No empty experience

Bullet length between 8–35 words

Numeric metrics presence (optional rule)

If failed:
→ auto re-prompt with correction instruction

Step 6: Rendering
HTML Templates

classic.html

modern.html

executive.html

Use Jinja2:

template.render(resume=ResumeDoc)
Step 7: PDF Generation

Using WeasyPrint:

HTML(string=html_content).write_pdf("resume.pdf")
Step 8: DOCX Generation

Using docxtpl:

doc = DocxTemplate("classic_template.docx")
doc.render(resume_dict)
doc.save("resume.docx")

This gives full layout control.

6. API Design
POST /resume/create

Request:

{
  "name": "",
  "email": "",
  "target_role": "",
  "design": "classic",
  "resume_file_url": ""
}

Response:

{
  "job_id": "",
  "status": "queued"
}
GET /resume/status/{job_id}

Response:

{
  "status": "processing|completed|failed",
  "download_pdf": "",
  "download_docx": "",
  "ats_score": 85
}
7. Database Schema
users

id

email

stripe_customer_id

plan

credits

created_at

resume_jobs

id

user_id

status

input_text

resume_json

audit_json

pdf_url

docx_url

created_at

8. Cost Optimization Strategy
Use LLM only for:

Parsing

Analysis

Optimization

Do NOT use LLM for:

Formatting

Layout

Math scoring

Date formatting

Keyword counting

Model Strategy
Task	Model
Parsing	GPT-4o-mini
Audit	GPT-4o-mini
Optimization	GPT-4o-mini
Premium rewrite	GPT-4o

Keep token budgets capped.

9. Quality Control Strategy

Strict JSON schemas

Deterministic templates

Validation + retry logic

Model version pinning

Logging + token tracking

Regression testing on sample resumes

10. Folder Structure
/app
    main.py
    config.py

/models
    resume_doc.py
    audit_schema.py

/services
    extractor.py
    parser.py
    auditor.py
    optimizer.py
    renderer.py
    storage.py
    email_service.py

/templates
    classic.html
    modern.html
    executive.html

/docx_templates
    classic.docx
    modern.docx
    executive.docx

/workers
    tasks.py

/tests
11. Deployment Plan
Phase 1

Deploy API to Fly.io or Render

Connect PostgreSQL

Connect Redis

Configure OpenAI API

Phase 2

Add Stripe billing

Add usage tracking

Add dashboard

Phase 3

Add JD matching engine

Add recruiter summary generator

Add LinkedIn summary tool

12. Monitoring

Track:

Tokens per request

Average job cost

Average processing time

Failure rate

Retry rate

Conversion rate

Revenue per user

13. Monetization Structure
Free

ATS score only

Limited tokens

No PDF export

Basic ($19)

Optimized resume

3 design choices

PDF + DOCX

Pro ($39)

JD match

Recruiter summary

Keyword boost

LinkedIn version

14. Long-Term Scalability

Future upgrades:

Model abstraction layer

Multi-LLM provider support

Fine-tuned resume model

Caching identical resumes

Prompt versioning

A/B testing prompt strategies

15. Guiding Principles

Structure > Free text

Validation > Blind trust

Templates > LLM formatting

Retry > Accept garbage

Metrics > Guessing

Clean contracts > Quick hacks

Final Note

If you build this correctly:

You control quality

You control cost

You control output

You can scale

You can sell confidently

You are not building an automation tool.

You are building an AI resume engine.