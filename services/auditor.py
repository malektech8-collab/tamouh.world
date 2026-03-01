import json
from pydantic import BaseModel
from typing import List, Optional
from services.parser import safe_llm_call
from models.resume_doc import ResumeDoc
from loguru import logger

class JDMatchResponse(BaseModel):
    match_score: int
    missing_keywords: List[str]
    strength_alignment: List[str]
    recommendations: List[str]
    recruiter_pitch: str
    interview_talking_points: List[str]

def calculate_jd_match(resume: ResumeDoc, jd: str) -> tuple[JDMatchResponse, int, float]:
    """
    Computes a deep contextual match between resume and JD.
    Includes recruiter findings and interview points.
    """
    logger.info("Computing deep JD match...")
    
    prompt = f"""
    Compare the following resume against the job description.
    Provide a realistic match score (0-100), identify missing critical keywords, 
    highlight areas of strong alignment, and provide a 3-line 'Recruiter Pitch' 
    explaining why this candidate is a fit (or not).
    Also, provide 3 strategic talking points for the candidate's interview.

    JOB DESCRIPTION:
    {jd}

    RESUME JSON:
    {resume.model_dump_json()}

    RETURN AS JSON ACCORDING TO THIS SCHEMA:
    {json.dumps(JDMatchResponse.model_json_schema(), indent=2)}
    """

    res_obj, tokens, cost = safe_llm_call(prompt, JDMatchResponse)
    return res_obj, tokens, cost
