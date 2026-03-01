from loguru import logger
import json
import time
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from app.config import settings
from app.exceptions import LLMError
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

MAX_ATTEMPTS = 3


def safe_llm_call(
    prompt: str,
    schema_model: Type[T],
    system_msg: Optional[str] = None
) -> tuple[T, int, float]:
    """
    Call the LLM with structured output, Pydantic validation, retries,
    and usage tracking.

    Retries up to MAX_ATTEMPTS times with exponential backoff (2^attempt
    seconds: 2s, 4s, 8s). Distinguishes transient API errors (rate limit,
    timeout) from permanent failures (validation, unexpected errors).

    Returns:
        Tuple of (validated_model, total_tokens, estimated_cost_usd)

    Raises:
        LLMError: When all retry attempts are exhausted.
    """
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt in range(MAX_ATTEMPTS):
        start_time = time.time()
        try:
            messages = []
            if system_msg:
                messages.append({"role": "system", "content": system_msg})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                response_format={"type": "json_object"},
                timeout=30,
            )

            content = response.choices[0].message.content
            usage = response.usage
            tokens = usage.total_tokens
            cost = (
                (usage.prompt_tokens * INPUT_COST_1K / 1000)
                + (usage.completion_tokens * OUTPUT_COST_1K / 1000)
            )

            validated_obj = schema_model.model_validate_json(content)

            duration = time.time() - start_time
            logger.info(
                "LLM call succeeded",
                model=schema_model.__name__,
                tokens=tokens,
                duration_s=round(duration, 2),
                attempt=attempt + 1,
            )
            return validated_obj, tokens, cost

        except ValidationError as e:
            # Pydantic validation failure — response structure was wrong.
            # These are often not transient; log and retry anyway in case the
            # model returns a valid structure on next attempt.
            logger.warning(
                "LLM response failed Pydantic validation",
                model=schema_model.__name__,
                attempt=attempt + 1,
                errors=e.error_count(),
            )
            last_exc = e

        except (RateLimitError, APITimeoutError) as e:
            logger.warning(
                "LLM transient error — will retry",
                error_type=type(e).__name__,
                attempt=attempt + 1,
            )
            last_exc = e

        except APIError as e:
            logger.warning(
                "LLM API error",
                error_type=type(e).__name__,
                status_code=getattr(e, "status_code", None),
                attempt=attempt + 1,
            )
            last_exc = e

        except Exception as e:
            logger.warning(
                "Unexpected error during LLM call",
                error_type=type(e).__name__,
                detail=str(e),
                attempt=attempt + 1,
            )
            last_exc = e

        # Exponential backoff before the next attempt (skip after last attempt)
        if attempt < MAX_ATTEMPTS - 1:
            sleep_secs = 2 ** (attempt + 1)
            logger.info("Retrying LLM call", sleep_s=sleep_secs, next_attempt=attempt + 2)
            time.sleep(sleep_secs)

    logger.error(
        "LLM call permanently failed",
        model=schema_model.__name__,
        attempts=MAX_ATTEMPTS,
        last_error=str(last_exc),
    )
    raise LLMError(
        f"AI call failed after {MAX_ATTEMPTS} attempts: {last_exc}"
    ) from last_exc


def parse_resume_text(text: str) -> tuple[ResumeDoc, int, float]:
    return safe_llm_call(text, ResumeDoc, system_msg=PARSE_PROMPT)


def audit_resume(resume: ResumeDoc, jd: Optional[str] = None) -> tuple[dict, int, float]:
    class AuditResponse(BaseModel):
        strengths: list[str]
        weaknesses: list[str]
        ats_score: int
        improvement_tips: list[str]

    jd_context = f" against this Job Description: {jd}" if jd else ""
    prompt = f"""
    Audit this resume{jd_context} for ATS optimization and clarity.

    RESUME JSON:
    {resume.model_dump_json()}

    RETURN AS JSON ACCORDING TO THIS SCHEMA:
    {json.dumps(AuditResponse.model_json_schema(), indent=2)}
    """

    res_obj, tokens, cost = safe_llm_call(prompt, AuditResponse)
    return res_obj.model_dump(), tokens, cost


def optimize_resume(resume: ResumeDoc, jd: str) -> tuple[ResumeDoc, int, float]:
    career_level = resume.meta.career_level or "senior"

    level_instruction = ""
    if career_level == "junior":
        level_instruction = "Focus on technical skills, internships, and projects. Use a proactive tone for early-career growth."
    elif career_level == "executive":
        level_instruction = "Focus on high-level strategic impact, P&L responsibility, team leadership, and multi-year transformation initiatives."
    else:
        level_instruction = "Focus on professional achievements, specialized domain expertise, and quantified project delivery."

    OPTIMIZE_PROMPT = f"""
    You are an expert resume writer. Optimize the following {career_level}-level resume JSON for this job description.
    Ensure you return ONLY a valid JSON object matching the ResumeDoc schema.

    {level_instruction}

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
