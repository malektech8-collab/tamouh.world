from fastapi import FastAPI, UploadFile, File, Form, Depends, Request
from app.config import settings
from workers.tasks import process_resume_job
from fastapi.staticfiles import StaticFiles
from app.database import engine, get_db, Base
from models.db_models import ResumeJob, User
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uuid
import os

# Initialize database tables
Base.metadata.create_all(bind=engine)

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.APP_NAME)

# Mount Static Folders
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}

@app.post("/resume/create")
@limiter.limit("5/minute")
async def create_resume_job(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(None),
    db: Session = Depends(get_db)
):
    job_id = str(uuid.uuid4())
    upload_dir = "/tmp/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{job_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    file_type = file.filename.split(".")[-1].lower()
    
    # Create job in database
    new_job = ResumeJob(
        id=job_id,
        status="queued",
        job_description=job_description
    )
    db.add(new_job)
    db.commit()
    
    # Trigger Celery task with JD
    process_resume_job.delay(job_id, file_path, file_type, job_description)
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/resume/status/{job_id}")
async def get_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
    if not job:
        return {"error": "Job not found"}
    
    # Simple progress logic for API
    progress = 0
    if job.status == "queued": progress = 10
    elif job.status == "processing": progress = 40
    elif job.status == "completed": progress = 100
    
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": progress,
        "resume": job.resume_json,
        "audit": job.audit_json,
        "pdf_url": job.pdf_url,
        "metrics": {
            "tokens": job.total_tokens,
            "estimated_cost": job.total_cost
        }
    }
