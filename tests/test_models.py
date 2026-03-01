from models.resume_doc import ResumeDoc

def test_resume_doc_validation():
    data = {
        "meta": {"language": "en", "design": "classic"},
        "profile": {"full_name": "Test User", "email": "test@example.com"},
        "skills": {"core": ["Testing"]},
        "experience": [],
        "education": [],
        "keywords": {}
    }
    doc = ResumeDoc(**data)
    assert doc.profile.full_name == "Test User"
    assert doc.meta.language == "en"

def test_invalid_email():
    import pytest
    from pydantic import ValidationError
    data = {
        "meta": {"language": "en"},
        "profile": {"full_name": "Test User", "email": "invalid-email"},
        "skills": {}, "experience": [], "education": [], "keywords": {}
    }
    with pytest.raises(ValidationError):
        ResumeDoc(**data)
