import time
import uuid
import os
from pathlib import Path
from datetime import timedelta

from fastapi import FastAPI, UploadFile, File, Form, Depends, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user
)
from app.config import settings
from app.database import engine, get_db, Base
from app.exceptions import AppError
from app.logging import configure_logging
from models.db_models import ResumeJob, User
from models.schemas import (
    UserRegisterRequest, UserLoginRequest, TokenResponse,
    UserResponse, UserRegisterResponse, ResumeJobResponse
)
from workers.tasks import process_resume_job

# ── Logging (must be first so all subsequent log calls are routed correctly) ──
configure_logging(settings)

# ── Database ──────────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.APP_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
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

# ── Static Files ──────────────────────────────────────────────────────────────
Path("static").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


# ── Request Logging Middleware ────────────────────────────────────────────────

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """
    Generate a trace ID per request, attach it to the request state,
    log the incoming request and outgoing response with timing.
    """
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id

    start = time.perf_counter()
    bound_logger = logger.bind(
        trace_id=trace_id,
        method=request.method,
        path=request.url.path,
    )
    bound_logger.debug("Request received")

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    bound_logger.info(
        "Request completed",
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    # Surface the trace ID in every response so callers can correlate errors
    response.headers["X-Trace-Id"] = trace_id
    return response


# ── Global Exception Handlers ─────────────────────────────────────────────────

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Return a structured JSON error for all known application exceptions."""
    trace_id = getattr(request.state, "trace_id", exc.trace_id)
    logger.bind(trace_id=trace_id).warning(
        "Application error",
        error_type=type(exc).__name__,
        status_code=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "trace_id": trace_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected exceptions — return 500 with trace ID."""
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    logger.bind(trace_id=trace_id).exception(
        "Unhandled exception",
        error_type=type(exc).__name__,
        path=str(request.url.path),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "trace_id": trace_id,
        },
    )


# ── Basic Routes ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.APP_NAME}


# ── Authentication Endpoints ──────────────────────────────────────────────────

@app.post("/auth/register", response_model=UserRegisterResponse)
async def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Returns:
        User data with JWT access token

    Raises:
        HTTPException 409: If email already exists
    """
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        email_domain = request.email.split("@")[-1]
        logger.warning("Registration failed — email already registered", email_domain=email_domain)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(request.password)

    new_user = User(
        id=user_id,
        email=request.email,
        hashed_password=hashed_pw,
        is_active=True,
        plan="free",
        credits=5
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(
        data={"sub": new_user.id},
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )

    email_domain = request.email.split("@")[-1]
    logger.info("User registered", user_id=new_user.id, email_domain=email_domain)

    return {
        "user": UserResponse.model_validate(new_user),
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.

    Returns:
        JWT access token with expiration

    Raises:
        HTTPException 401: If credentials are invalid
        HTTPException 403: If account is inactive
    """
    email_domain = request.email.split("@")[-1]
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        logger.warning(
            "Login failed — invalid credentials",
            email_domain=email_domain,
            reason="bad_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning("Login failed — inactive account", user_id=user.id, email_domain=email_domain)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )
    expires_in = settings.JWT_EXPIRATION_HOURS * 3600

    logger.info("Login successful", user_id=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in
    }


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh an expired JWT token."""
    access_token = create_access_token(
        data={"sub": current_user.id},
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRATION_HOURS * 3600
    }


@app.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ── Resume Endpoints ──────────────────────────────────────────────────────────

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

    Returns:
        Job ID and initial status ("queued")
    """
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file_content = await file.read()

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    ALLOWED_EXTENSIONS = {".pdf", ".docx"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    if file_ext == ".pdf" and not file_content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    if job_description and len(job_description) > 50000:
        raise HTTPException(status_code=400, detail="Job description too long (max 50KB)")

    job_id = str(uuid.uuid4())
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    Path(upload_dir).mkdir(exist_ok=True)

    safe_filename = f"{job_id}{file_ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    try:
        Path(file_path).resolve().relative_to(Path(upload_dir).resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    with open(file_path, "wb") as buffer:
        buffer.write(file_content)

    file_type = file_ext.lstrip(".")

    new_job = ResumeJob(
        id=job_id,
        user_id=current_user.id,
        status="queued",
        job_description=job_description
    )
    db.add(new_job)
    db.commit()

    logger.info(
        "Resume job queued",
        job_id=job_id,
        user_id=current_user.id,
        file_type=file_type,
        has_jd=bool(job_description),
    )

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

    Raises:
        HTTPException 404: If job not found or user doesn't own it
    """
    job = db.query(ResumeJob).filter(
        ResumeJob.id == job_id,
        ResumeJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or access denied"
        )

    progress = {"queued": 10, "processing": 40, "completed": 100}.get(job.status, 0)

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
    """List all resume jobs for the current user, newest first."""
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
