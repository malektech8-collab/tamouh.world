from celery import Celery
from typing import Optional
from app.config import settings
from services.extractor import extract_text_from_pdf, extract_text_from_docx
from services.parser import parse_resume_text, audit_resume, optimize_resume
from services.auditor import calculate_jd_match
from services.classifier import classify_career_level
from app.exceptions import ExtractionError, LLMError, ProcessingError, PdfGenerationError
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from app.database import SessionLocal
from models.db_models import ResumeJob
from loguru import logger
import uuid
import os

celery_app = Celery("resume_worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
env = Environment(loader=FileSystemLoader("templates"))

_MAX_ERROR_LEN = 500  # Characters stored in DB; prevents unbounded error messages


@celery_app.task(name="process_resume_job")
def process_resume_job(
    job_id: str,
    file_path: str,
    file_type: str,
    job_description: Optional[str] = None
):
    # Bind a trace ID so every log line from this job is correlated
    trace_id = str(uuid.uuid4())
    log = logger.bind(job_id=job_id, trace_id=trace_id)
    log.info("Resume job started", file_type=file_type, has_jd=bool(job_description))

    db = SessionLocal()
    job = None  # Initialise before try so except block can always reference it
    current_step = "startup"

    try:
        # ── Step 1: Mark job as processing ────────────────────────────────────
        current_step = "db_update"
        job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
        if job:
            job.status = "processing"
            db.commit()

        # ── Step 2: Extract text ───────────────────────────────────────────────
        current_step = "extraction"
        if file_type == "pdf":
            text = extract_text_from_pdf(file_path)
        elif file_type == "docx":
            text = extract_text_from_docx(file_path)
        else:
            raise ExtractionError(f"Unsupported file type: {file_type}")

        log.info("Text extracted", chars=len(text))

        total_tokens = 0
        total_cost = 0.0

        # ── Step 3: Parse into structured resume ───────────────────────────────
        current_step = "parsing"
        resume, tokens, cost = parse_resume_text(text)
        total_tokens += tokens
        total_cost += cost
        log.info("Resume parsed", tokens=tokens)

        # ── Step 3.5: Career classification ───────────────────────────────────
        current_step = "classification"
        level, conf = classify_career_level(resume)
        resume.meta.career_level = level
        resume.meta.confidence = conf
        log.info("Career level classified", level=level, confidence=round(conf, 2))

        match_data = None

        # ── Step 4: JD matching + optimisation ────────────────────────────────
        if job_description:
            current_step = "optimization"
            resume, tokens, cost = optimize_resume(resume, job_description)
            total_tokens += tokens
            total_cost += cost
            log.info("Resume optimised for JD", tokens=tokens)

            current_step = "jd_match"
            match_data, tokens, cost = calculate_jd_match(resume, job_description)
            total_tokens += tokens
            total_cost += cost
            log.info("JD match scored", tokens=tokens)

        # ── Step 5: Audit ──────────────────────────────────────────────────────
        current_step = "audit"
        audit, tokens, cost = audit_resume(resume, jd=job_description)
        total_tokens += tokens
        total_cost += cost
        log.info("Audit completed", tokens=tokens)

        # ── Step 6: HTML rendering ─────────────────────────────────────────────
        current_step = "rendering"
        template = env.get_template("classic.html")
        html_content = template.render(resume=resume)

        # ── Step 7: PDF generation ─────────────────────────────────────────────
        current_step = "pdf_generation"
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = f"{output_dir}/{job_id}.pdf"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html_content)
                page.pdf(path=pdf_path, format="A4", print_background=True)
                browser.close()
        except Exception as e:
            raise PdfGenerationError(f"Playwright PDF generation failed: {e}") from e

        # ── Step 8: Persist results ────────────────────────────────────────────
        current_step = "db_save"
        if job:
            job.status = "completed"
            job.resume_json = resume.model_dump()
            job.audit_json = audit
            job.match_json = match_data.model_dump() if match_data else None
            job.pdf_url = pdf_path
            job.total_tokens = total_tokens
            job.total_cost = f"{total_cost:.5f}"
            db.commit()

        log.info("Job completed", total_tokens=total_tokens, total_cost=f"${total_cost:.4f}")
        return {"status": "completed"}

    except (ExtractionError, LLMError, ProcessingError, PdfGenerationError) as e:
        # Known typed errors — log at ERROR with context
        log.error(
            "Job failed (known error)",
            error_type=type(e).__name__,
            step=current_step,
            detail=str(e),
        )
        db.rollback()
        if job:
            error_msg = f"[{current_step}] {str(e)}"[:_MAX_ERROR_LEN]
            job.status = "failed"
            job.error_message = error_msg
            db.commit()
        return {"status": "failed", "error": str(e), "step": current_step}

    except Exception as e:
        # Unexpected errors — log with full traceback
        log.exception(
            "Job failed (unexpected error)",
            step=current_step,
            error_type=type(e).__name__,
        )
        db.rollback()
        if job:
            error_msg = f"[{current_step}] Unexpected error: {str(e)}"[:_MAX_ERROR_LEN]
            job.status = "failed"
            job.error_message = error_msg
            db.commit()
        return {"status": "failed", "error": str(e), "step": current_step}

    finally:
        db.close()
