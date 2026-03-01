from models.resume_doc import ResumeDoc
from typing import Tuple, List
import re
from datetime import datetime
from loguru import logger

from app.exceptions import ProcessingError


def calculate_years(experience_list: List) -> float:
    """Deterministic calculation of years of experience from start/end dates."""
    total_months = 0
    now = datetime.now()

    for exp in experience_list:
        try:
            start_str = str(exp.start)
            end_str = (
                str(exp.end)
                if exp.end and str(exp.end).lower() != "present"
                else now.strftime("%Y-%m")
            )

            start_search = re.findall(r'(\d{4})', start_str)
            end_search = re.findall(r'(\d{4})', end_str)

            if start_search and end_search:
                s_year = int(start_search[0])
                e_year = int(end_search[0])
                total_months += (e_year - s_year) * 12

        except Exception as e:
            logger.warning(
                "Year calculation failed for experience entry — skipping",
                error=str(e),
                entry=str(exp)[:200],
            )
            continue

    return round(total_months / 12, 1)


def detect_leadership(resume: ResumeDoc) -> int:
    """Scans titles and bullets for leadership signals (Manager, Director, VP, etc)."""
    signals = [
        "manager", "director", "head of", "lead", "vp", "chief",
        "cto", "ceo", "cfo", "oversaw", "managed", "led team"
    ]
    try:
        full_text = resume.model_dump_json().lower()
    except Exception as e:
        logger.warning("Leadership detection failed — returning 0", error=str(e))
        return 0

    score = 0
    for signal in signals:
        if signal in full_text:
            score += 1
    return score


def count_metrics(resume: ResumeDoc) -> float:
    """Counts quantified metrics (%, $, numbers) to calculate density."""
    metric_patterns = [
        r'\d+%', r'\$\d+', r'\d+\sSAR', r'\d+',
        r'increased', r'decreased', r'revenue', r'saved'
    ]
    count = 0
    total_bullets = 0

    try:
        for exp in resume.experience:
            for bullet in exp.bullets:
                total_bullets += 1
                for pattern in metric_patterns:
                    if re.search(pattern, bullet.lower()):
                        count += 1
                        break
    except Exception as e:
        logger.warning("Metrics counting failed — returning 0.0", error=str(e))
        return 0.0

    if total_bullets == 0:
        return 0.0
    return count / total_bullets


def classify_career_level(resume: ResumeDoc) -> Tuple[str, float]:
    """
    Hybrid classifier combining years, leadership, and metrics signals.

    Raises:
        ProcessingError: If classification fails entirely.
    """
    try:
        score = 0
        years = calculate_years(resume.experience)
        leadership = detect_leadership(resume)
        metrics_density = count_metrics(resume)

        if years <= 3:
            score += 1
        elif 4 <= years <= 10:
            score += 2
        else:
            score += 3

        if leadership >= 5:
            score += 3
        elif leadership >= 2:
            score += 2

        if metrics_density > 0.5:
            score += 2

        logger.info(
            "Career classification complete",
            years=years,
            leadership=leadership,
            metrics_density=round(metrics_density, 2),
            total_score=score,
        )

        if score <= 3:
            return "junior", 0.90
        elif score <= 6:
            return "senior", 0.85
        else:
            return "executive", 0.80

    except Exception as e:
        raise ProcessingError(f"Career classification failed: {e}") from e
