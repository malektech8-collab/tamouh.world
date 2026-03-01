from fastapi import FastAPI, UploadFile, File, Form, Depends, Request, HTTPException, status
from app.config import settings
from workers.tasks import process_resume_job
from fastapi.staticfiles import StaticFiles
from app.database import engine, get_db, Base
from models.db_models import ResumeJob, User
from models.schemas import (
    UserRegisterRequest, UserLoginRequest, TokenResponse,
    UserResponse, UserRegisterResponse, ResumeJobResponse
)
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user
)
from pathlib import Path
from datetime import timedelta
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


# ===== AUTHENTICATION ENDPOINTS =====

@app.post("/auth/register", response_model=UserRegisterResponse)
async def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Args:
        request: User registration data (email, password)
        db: Database session

    Returns:
        User data with JWT access token

    Raises:
        HTTPException: If email already exists
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create new user
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(request.password)

    new_user = User(
        id=user_id,
        email=request.email,
        hashed_password=hashed_password,
        is_active=True,
        plan="free",
        credits=5  # Free tier credits
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT token
    access_token = create_access_token(
        data={"sub": new_user.id},
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )

    return {
        "user": UserResponse.from_orm(new_user),
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.

    Args:
        request: Login credentials (email, password)
        db: Database session

    Returns:
        JWT access token with expiration

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Generate JWT token
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )

    expires_in = settings.JWT_EXPIRATION_HOURS * 3600  # Convert to seconds

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in
    }


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """
    Refresh an expired JWT token.

    Args:
        current_user: Current authenticated user

    Returns:
        New JWT access token
    """
    access_token = create_access_token(
        data={"sub": current_user.id},
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )

    expires_in = settings.JWT_EXPIRATION_HOURS * 3600

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in
    }


@app.post("/auth/resume")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user info.

    Args:
        current_user: Current authenticated user

    Returns:
        User data
    """
    return UserResponse.from_orm(current_user)


# ===== RESUME ENDPOINTS =====

@app.post("/resume/create")
@limiter.limit("5/minute")
async def create_resume_job(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a resume processing job with file validation.

    Args:
        file: Resume file (PDF or DOCX)
        job_description: Optional job description for matching
        current_user: Current authenticated user
        db: Database session

    Returns:
        Job ID and status
    """
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
    
    # Create job in database (linked to current user)
    new_job = ResumeJob(
        id=job_id,
        user_id=current_user.id,  # Link to authenticated user
        status="queued",
        job_description=job_description
    )
    db.add(new_job)
    db.commit()
    
    # Trigger Celery task with JD
    process_resume_job.delay(job_id, file_path, file_type, job_description)
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/resume/status/{job_id}", response_model=ResumeJobResponse)
async def get_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get resume processing job status.

    Args:
        job_id: Resume job ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Job status, results, and metrics

    Raises:
        HTTPException: If job not found or user doesn't own it
    """
    # Verify user owns this job
    job = db.query(ResumeJob).filter(
        ResumeJob.id == job_id,
        ResumeJob.user_id == current_user.id  # User isolation
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or access denied"
        )

    # Simple progress logic for API
    progress = 0
    if job.status == "queued":
        progress = 10
    elif job.status == "processing":
        progress = 40
    elif job.status == "completed":
        progress = 100

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": progress,
        "resume": job.resume_json,
        "audit": job.audit_json,
        "pdf_url": job.pdf_url,
        "error": job.error_message,
        "metrics": {
            "tokens": job.total_tokens,
            "estimated_cost": job.total_cost
        }
    }


@app.get("/my-resumes")
async def list_user_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all resumes for the current user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of user's resume jobs
    """
    jobs = db.query(ResumeJob).filter(
        ResumeJob.user_id == current_user.id
    ).order_by(ResumeJob.created_at.desc()).all()

    return [
        {
            "job_id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "pdf_url": job.pdf_url,
            "error": job.error_message
        }
        for job in jobs
    ]
