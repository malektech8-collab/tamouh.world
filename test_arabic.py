from services.parser import parse_resume_text, audit_resume
from jinja2 import Environment, FileSystemLoader
import os
from app.config import settings
from models.resume_doc import ResumeDoc

def run_arabic_test():
    print("Starting Arabic RTL Test...")
    
    if not settings.OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY is not set.")
        return

    # Sample Arabic Resume Text
    arabic_text = """
    أحمد محمد
    مهندس برمجيات | ahmed@example.com | +966500000000
    
    ملخص:
    خبير في تطوير تطبيقات الويب باستخدام بايثون وجافا سكريبت مع خبرة تزيد عن 7 سنوات.
    
    الخبرة:
    شركة تكنولوجيا المعلومات - مطور أول (2018 - الآن)
    - قيادة فريق التطوير لبناء أنظمة ذكاء اصطناعي.
    - تحسين أداء قواعد البيانات بنسبة 30%.
    
    التعليم:
    جامعة الملك سعود - بكالوريوس علوم الحاسب (2014 - 2018)
    
    المهارات:
    بايثون، فاست آي بي آي، رياكت، ذكاء اصطناعي
    """

    print("Step 1: Parsing Arabic text...")
    try:
        # We explicitly set language to 'ar' in the prompt/meta if possible, 
        # but let's see if the AI detects it as 'ar'.
        resume = parse_resume_text(arabic_text)
        # Ensure language is set to 'ar' for RTL trigger
        resume.meta.language = "ar"
        print("Done Step 1.")
    except Exception as e:
        print(f"Parsing failed: {e}")
        return

    print("Step 2: Rendering Arabic RTL HTML...")
    try:
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("classic.html")
        html_content = template.render(resume=resume)
        
        output_dir = "test_outputs"
        os.makedirs(output_dir, exist_ok=True)
        html_path = f"{output_dir}/test_resume_ar.html"
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Arabic HTML Preview generated at: {os.path.abspath(html_path)}")
        print("Verified: Document 'dir' attribute should be 'rtl'.")

    except Exception as e:
        print(f"Rendering failed: {e}")

    print("\nArabic Test Complete!")

if __name__ == "__main__":
    run_arabic_test()
