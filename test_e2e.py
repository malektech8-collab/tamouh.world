from services.parser import parse_resume_text, audit_resume
from jinja2 import Environment, FileSystemLoader
import os
from app.config import settings
from models.resume_doc import ResumeDoc

def run_test():
    print("Starting End-to-End Test (Synchronous)...")
    
    # Check for API Key
    if not settings.OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY is not set.")
        return

    # Sample Resume Text (simulating extraction)
    sample_text = """
    MALEK TECH
    Software Engineer | malek@example.com | +123456789
    
    Summary:
    Expert in Python and AI integration with 5 years of experience.
    
    Experience:
    Google - Senior Developer (2020 - Present)
    - Led AI team to build agentic coding systems.
    - Optimized backend performance by 40%.
    
    Education:
    MIT - B.S. in Computer Science (2016 - 2020)
    
    Skills:
    Python, FastAPI, Redis, OpenAI, SQL
    """

    print("Step 1: Parsing with GPT-4o-mini...")
    try:
        resume = parse_resume_text(sample_text)
        print(f"Parsed Resume for: {resume.profile.full_name}")
    except Exception as e:
        print(f"Parsing failed: {e}")
        return

    print("Step 2: Auditing...")
    try:
        audit = audit_resume(resume)
        print(f"Audit generated successfully.")
    except Exception as e:
        print(f"Audit failed: {e}")
        # Continue anyway, let's see rendering

    print("Step 3: Rendering (HTML & PDF)...")
    try:
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("classic.html")
        html_content = template.render(resume=resume)
        
        output_dir = "test_outputs"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save HTML anyway
        html_path = f"{output_dir}/test_resume.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML Preview generated at: {os.path.abspath(html_path)}")

        try:
            from weasyprint import HTML
            pdf_path = f"{output_dir}/test_resume.pdf"
            HTML(string=html_content).write_pdf(pdf_path)
            print(f"PDF generated at: {os.path.abspath(pdf_path)}")
        except Exception as pdf_err:
            print(f"PDF generation skipped: {pdf_err}")
            print("Tip: WeasyPrint on Windows requires GTK+ libraries. HTML preview is available.")

    except Exception as e:
        print(f"Rendering failed: {e}")

    print("\nTest Complete!")

if __name__ == "__main__":
    run_test()
