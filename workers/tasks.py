from celery import Celery
from app.config import settings
from services.extractor import extract_text_from_pdf, extract_text_from_docx
from services.parser import parse_resume_text, audit_resume
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import os

celery_app = Celery("resume_worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
env = Environment(loader=FileSystemLoader("templates"))

@celery_app.task(name="process_resume_job")
def process_resume_job(job_id: str, file_path: str, file_type: str):
    try:
        # Step 1: Extract
        if file_type == "pdf":
            text = extract_text_from_pdf(file_path)
        elif file_type == "docx":
            text = extract_text_from_docx(file_path)
        else:
            raise ValueError("Unsupported file type")

        # Step 2: Parse to ResumeDoc
        resume = parse_resume_text(text)
        
        # Step 3: Audit
        audit = audit_resume(resume)
        
        # Step 4: Rendering to HTML
        template = env.get_template("classic.html")
        html_content = template.render(resume=resume)
        
        # Step 5: PDF Generation
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = f"{output_dir}/{job_id}.pdf"
        
        HTML(string=html_content).write_pdf(pdf_path)
        
        return {
            "status": "completed",
            "resume": resume.model_dump(),
            "audit": audit,
            "pdf_url": pdf_path
        }
        
    except Exception as e:
        print(f"Job {job_id} failed: {str(e)}")
        return {"status": "failed", "error": str(e)}
