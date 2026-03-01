from celery import Celery
from typing import Optional
from app.config import settings
from services.extractor import extract_text_from_pdf, extract_text_from_docx
from services.parser import parse_resume_text, audit_resume, optimize_resume
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from app.database import SessionLocal
from models.db_models import ResumeJob
import os

celery_app = Celery("resume_worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
env = Environment(loader=FileSystemLoader("templates"))

@celery_app.task(name="process_resume_job")
def process_resume_job(job_id: str, file_path: str, file_type: str, job_description: Optional[str] = None):
    db = SessionLocal()
    try:
        # Step 1: Update Status in DB (Update existing job)
        job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
        if job:
            job.status = "processing"
            db.commit()

        # Step 2: Extract
        if file_type == "pdf":
            text = extract_text_from_pdf(file_path)
        elif file_type == "docx":
            text = extract_text_from_docx(file_path)
        else:
            raise ValueError("Unsupported file type")

        # Step 3: Parse & Optimize
        resume = parse_resume_text(text)
        
        # If JD provided, optimize it
        if job_description:
            resume = optimize_resume(resume, job_description)
        
        # Step 4: Audit
        audit = audit_resume(resume, jd=job_description)
        
        # Step 5: Rendering
        template = env.get_template("classic.html")
        html_content = template.render(resume=resume)
        
        # Step 6: PDF Generation
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = f"{output_dir}/{job_id}.pdf"
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content)
            page.pdf(path=pdf_path, format="A4", print_background=True)
            browser.close()
        
        # Step 7: Update Job in DB
        if job:
            job.status = "completed"
            job.resume_json = resume.model_dump()
            job.audit_json = audit
            job.pdf_url = pdf_path
            db.commit()
        
        return {
            "status": "completed",
            "pdf_url": pdf_path
        }
        
    except Exception as e:
        print(f"Job {job_id} failed: {str(e)}")
        if job:
            job.status = "failed"
            db.commit()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
