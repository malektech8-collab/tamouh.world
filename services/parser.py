import json
from openai import OpenAI
from app.config import settings
from models.resume_doc import ResumeDoc

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Generate schema once
SCHEMA = ResumeDoc.model_json_schema()

PARSE_PROMPT = f"""
You are an expert resume parser. Extract the information from the raw resume text into the following JSON format.
Ensure you follow the structure strictly. Never invent experience.
If a section is missing, return an empty list or null as appropriate.

JSON SCHEMA:
{json.dumps(SCHEMA, indent=2)}
"""

def parse_resume_text(text: str) -> ResumeDoc:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": PARSE_PROMPT},
            {"role": "user", "content": text}
        ],
        response_format={"type": "json_object"}
    )
    
    parsed_data = json.loads(response.choices[0].message.content)
    return ResumeDoc(**parsed_data)

def audit_resume(resume: ResumeDoc) -> dict:
    # Separate prompt for auditing logic
    AUDIT_PROMPT = f"Audit this resume for ATS optimization and clarity. Return the findings as JSON: {resume.model_dump_json()}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": AUDIT_PROMPT}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
