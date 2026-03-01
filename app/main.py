from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from app.config import settings
from workers.tasks import process_resume_job
import uuid
import os

app = FastAPI(title=settings.APP_NAME)

@app.get("/")
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}

@app.post("/resume/create")
async def create_resume_job(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    upload_dir = "/tmp/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{job_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    file_type = file.filename.split(".")[-1].lower()
    
    # Trigger Celery task
    process_resume_job.delay(job_id, file_path, file_type)
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/resume/status/{job_id}")
async def get_status(job_id: str):
    # This will eventually read from a real DB
    from workers.tasks import celery_app
    res = celery_app.AsyncResult(job_id)
    
    if res.ready():
        return {"job_id": job_id, "status": "completed", "result": res.result}
    else:
        return {"job_id": job_id, "status": "processing"}
