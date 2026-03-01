from services.parser import parse_resume_text, optimize_resume, audit_resume
from jinja2 import Environment, FileSystemLoader
import os
import asyncio
from playwright.async_api import async_playwright
from app.config import settings
from models.resume_doc import ResumeDoc

def run_jd_test():
    print("Starting JD Optimization Test...")
    
    if not settings.OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY is not set.")
        return

    # Sample Resume 
    resume_text = """
    John Doe
    Python Developer | john.doe@example.com
    5 years of experience building web applications with Django and Flask.
    """

    # Sample JD
    jd_text = """
    We are looking for a FastAPI expert who can build scalable AI pipelines with Redis and Celery.
    Experience with Pydantic and AWS is a plus.
    """

    try:
        print("Step 1: Parsing original resume...")
        resume = parse_resume_text(resume_text)
        
        print("Step 2: Optimizing against JD (Headless)...")
        optimized_resume = optimize_resume(resume, jd_text)
        
        print("Step 3: Auditing optimized resume...")
        audit = audit_resume(optimized_resume, jd=jd_text)
        
        print(f"Optimization Results:")
        print(f"Original Skills: {resume.skills.get('core', [])}")
        print(f"Optimized Skills: {optimized_resume.skills.get('core', [])}")
        
        # Verify keywords from JD appear
        keywords = optimized_resume.keywords.get("included", [])
        print(f"Included Keywords: {keywords}")

        # Rendering
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("classic.html")
        html_content = template.render(resume=optimized_resume)
        
        output_dir = "test_outputs"
        os.makedirs(output_dir, exist_ok=True)
        html_path = f"{output_dir}/optimized_resume.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"Optimized HTML Preview: {os.path.abspath(html_path)}")

    except Exception as e:
        print(f"JD Optimization Test failed: {e}")

if __name__ == "__main__":
    run_jd_test()
