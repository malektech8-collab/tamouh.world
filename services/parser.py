from loguru import logger
import json
import time
from typing import Optional, Type, TypeVar
from pydantic import BaseModel
from openai import OpenAI
from app.config import settings
from models.resume_doc import ResumeDoc

T = TypeVar('T', bound=BaseModel)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Cost constants for GPT-4o-mini (estimates per 1k tokens)
INPUT_COST_1K = 0.00015
OUTPUT_COST_1K = 0.0006

# Generate schema once
SCHEMA = ResumeDoc.model_json_schema()

PARSE_PROMPT = f"""
You are an expert resume parser. Extract the information from the raw resume text into the following JSON format.
Ensure you follow the structure strictly. Never invent experience.
If a section is missing, return an empty list or null as appropriate.

JSON SCHEMA:
{json.dumps(SCHEMA, indent=2)}
"""

def safe_llm_call(prompt: str, schema_model: Type[T], system_msg: Optional[str] = None) -> tuple[T, int, float]:
    """Calls LLM with structured output, validation, retries, and usage tracking."""
    attempts = 3
    for i in range(attempts):
        start_time = time.time()
        try:
            messages = []
            if system_msg:
                messages.append({"role": "system", "content": system_msg})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            usage = response.usage
            tokens = usage.total_tokens
            cost = (usage.prompt_tokens * INPUT_COST_1K / 1000) + (usage.completion_tokens * OUTPUT_COST_1K / 1000)
            
            # Validate with Pydantic
            validated_obj = schema_model.model_validate_json(content)
            
            duration = time.time() - start_time
            logger.info(f"LLM Call Success | Model: {schema_model.__name__} | Tokens: {tokens} | Dur: {duration:.2f}s | Attempt: {i+1}")
            
            return validated_obj, tokens, cost
            
        except Exception as e:
            logger.warning(f"LLM Call Attempt {i+1} Failed: {str(e)}")
            if i == attempts - 1:
                logger.error(f"LLM Call Permanently Failed for {schema_model.__name__}")
                raise Exception(f"AI structure validation failed after {attempts} attempts.")
            time.sleep(1) # Basic backoff

def parse_resume_text(text: str) -> tuple[ResumeDoc, int, float]:
    return safe_llm_call(text, ResumeDoc, system_msg=PARSE_PROMPT)

def audit_resume(resume: ResumeDoc, jd: Optional[str] = None) -> tuple[dict, int, float]:
    jd_context = f" against this Job Description: {jd}" if jd else ""
    prompt = f"Audit this resume{jd_context} for ATS optimization and clarity. Return the findings as JSON: {resume.model_dump_json()}"
    
    # Simple Audit Wrapper (since audit is a dict, we could define a specific model if needed)
    class AuditResponse(BaseModel):
        strengths: list[str]
        weaknesses: list[str]
        ats_score: int
        improvement_tips: list[str]

    res_obj, tokens, cost = safe_llm_call(prompt, AuditResponse)
    return res_obj.model_dump(), tokens, cost

def optimize_resume(resume: ResumeDoc, jd: str) -> tuple[ResumeDoc, int, float]:
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
    return safe_llm_call(OPTIMIZE_PROMPT, ResumeDoc)
