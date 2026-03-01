from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict

class Profile(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    portfolio: Optional[str] = None

class Experience(BaseModel):
    company: str
    title: str
    location: Optional[str] = None
    start: str
    end: Optional[str] = "Present"
    bullets: List[str]

class Education(BaseModel):
    institution: str
    degree: str
    field: Optional[str] = None
    start: str
    end: str
    details: List[str] = []

class Meta(BaseModel):
    language: str = "en"
    target_role: Optional[str] = ""
    design: str = "classic"
    ats_level: str = "strict"
    career_level: Optional[str] = "senior" # junior, senior, executive
    auto_detected: bool = True
    confidence: float = 0.0
    user_override: Optional[str] = None

class ResumeDoc(BaseModel):
    meta: Meta
    profile: Profile
    headline: Optional[str] = None
    summary: Optional[str] = None
    skills: Dict[str, List[str]]
    experience: List[Experience]
    education: List[Education]
    certifications: List[str] = []
    projects: List[Dict] = []
    languages: List[str] = []
    achievements: List[str] = []
    keywords: Dict[str, List[str]] = {"included": [], "missing": []}
