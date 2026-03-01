from fastapi import FastAPI, UploadFile, File, Form, Depends, Request, HTTPException
from app.config import settings
from workers.tasks import process_resume_job
from fastapi.staticfiles import StaticFiles
from app.database import engine, get_db, Base
from models.db_models import ResumeJob, User
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uuid
import os

# Initialize database tables
Base.metadata.create_all(bind=engine)

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.APP_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
if settings.ENVIRONMENT == "production":
    cors_origins = os.getenv("CORS_ORIGINS", "https://yourdomain.com").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Mount Static Folders
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.APP_NAME}

@app.post("/resume/create")
@limiter.limit("5/minute")
async def create_resume_job(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(None),
    db: Session = Depends(get_db)
):
    """Create a resume processing job with file validation."""
    # File size validation (50 MB max)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file_content = await file.read()

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
        )

    # File type validation
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validate PDF content
    if file_ext == ".pdf" and not file_content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    # Validate job description length
    if job_description and len(job_description) > 50000:
        raise HTTPException(
            status_code=400,
            detail="Job description too long (max 50KB)"
        )

    # Generate safe filename
    job_id = str(uuid.uuid4())
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    Path(upload_dir).mkdir(exist_ok=True)

    safe_filename = f"{job_id}{file_ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    # Ensure path is within upload directory
    try:
        Path(file_path).resolve().relative_to(Path(upload_dir).resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Write file
    with open(file_path, "wb") as buffer:
        buffer.write(file_content)

    file_type = file_ext.lstrip(".")
    
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
    """Get resume processing job status."""
    job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
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
