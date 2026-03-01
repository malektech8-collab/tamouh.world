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

def audit_resume(resume: ResumeDoc, jd: Optional[str] = None) -> dict:
    # Separate prompt for auditing logic
    jd_context = f" against this Job Description: {jd}" if jd else ""
    AUDIT_PROMPT = f"Audit this resume{jd_context} for ATS optimization and clarity. Return the findings as JSON: {resume.model_dump_json()}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": AUDIT_PROMPT}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def optimize_resume(resume: ResumeDoc, jd: str) -> ResumeDoc:
    OPTIMIZE_PROMPT = f"""
    You are an expert resume writer. Optimize the following resume JSON for this job description.
    Ensure you return ONLY a valid JSON object matching the ResumeDoc schema.
    
    1. Rewrite professional experience bullets to highlight relevance to the JD.
    2. Quantify achievements (use percentages and numbers where possible).
    3. Update the 'keywords.included' list with matching keywords from the JD.
    4. Keep all factual data like dates and institutions identical.
    
    JOB DESCRIPTION:
    {jd}
    
    ORIGINAL RESUME JSON:
    {resume.model_dump_json()}
    
    JSON SCHEMA FOR OUTPUT:
    {json.dumps(SCHEMA, indent=2)}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": OPTIMIZE_PROMPT}],
        response_format={"type": "json_object"}
    )
    
    optimized_data = json.loads(response.choices[0].message.content)
    return ResumeDoc(**optimized_data)
