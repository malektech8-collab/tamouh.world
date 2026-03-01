from services.parser import parse_resume_text, audit_resume, optimize_resume
from services.auditor import calculate_jd_match
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from app.database import SessionLocal
from models.db_models import ResumeJob
from loguru import logger
import os

celery_app = Celery("resume_worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
env = Environment(loader=FileSystemLoader("templates"))

@celery_app.task(name="process_resume_job")
def process_resume_job(job_id: str, file_path: str, file_type: str, job_description: Optional[str] = None):
    logger.info(f"Starting Resume Job {job_id} | Type: {file_type} | Has JD: {bool(job_description)}")
    db = SessionLocal()
    try:
        # Step 1: Update Status in DB
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

        # Metrics Tracking
        total_tokens = 0
        total_cost = 0.0

        # Step 3: Initial Parsing
        resume, tokens, cost = parse_resume_text(text)
        total_tokens += tokens
        total_cost += cost
        
        match_data = None
        
        # Step 4: JD Match & Optimization (Intelligence Layer)
        if job_description:
            # 4.1 Optimization pass
            resume, tokens, cost = optimize_resume(resume, job_description)
            total_tokens += tokens
            total_cost += cost
            
            # 4.2 Deep match pass (Phase 5)
            match_data, tokens, cost = calculate_jd_match(resume, job_description)
            total_tokens += tokens
            total_cost += cost
        
        # Step 5: Audit
        audit, tokens, cost = audit_resume(resume, jd=job_description)
        total_tokens += tokens
        total_cost += cost
        
        # Step 6: Rendering
        template = env.get_template("classic.html")
        html_content = template.render(resume=resume)
        
        # Step 7: PDF Generation
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = f"{output_dir}/{job_id}.pdf"
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content)
            page.pdf(path=pdf_path, format="A4", print_background=True)
            browser.close()
        
        # Step 8: Final DB Update
        if job:
            job.status = "completed"
            job.resume_json = resume.model_dump()
            job.audit_json = audit
            job.match_json = match_data.model_dump() if match_data else None
            job.pdf_url = pdf_path
            job.total_tokens = total_tokens
            job.total_cost = f"{total_cost:.5f}"
            db.commit()
            logger.info(f"Job {job_id} Completed Successfully | Cost: ${total_cost:.4f}")
        
        return {"status": "completed"}
        
    except Exception as e:
        logger.error(f"Critical Failure Job {job_id}: {str(e)}")
        if job:
            job.status = "failed"
            db.commit()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
