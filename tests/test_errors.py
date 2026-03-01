"""
Tests for error handling infrastructure (Phase 3).

Covers:
- Custom exception hierarchy
- Global exception handlers (AppError → structured JSON response)
- ExtractionError raised by extractor service
- Auth event logging (no passwords in log output)
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.exceptions import (
    AppError,
    ExtractionError,
    LLMError,
    ProcessingError,
    PdfGenerationError,
)


# ── Custom Exception Tests ────────────────────────────────────────────────────

@pytest.mark.unit
class TestCustomExceptions:
    """Test the exception hierarchy and its attributes."""

    def test_extraction_error_status_400(self):
        exc = ExtractionError("PDF corrupted")
        assert exc.status_code == 400
        assert exc.detail == "PDF corrupted"
        assert exc.trace_id is not None
        assert len(exc.trace_id) > 10

    def test_llm_error_status_502(self):
        exc = LLMError("OpenAI unreachable")
        assert exc.status_code == 502
        assert "OpenAI" in exc.detail

    def test_processing_error_status_500(self):
        exc = ProcessingError("Classifier blew up")
        assert exc.status_code == 500

    def test_pdf_generation_error_status_500(self):
        exc = PdfGenerationError("Playwright crashed")
        assert exc.status_code == 500

    def test_app_error_auto_generates_trace_id(self):
        exc = AppError("something broke")
        assert exc.trace_id is not None
        # UUID v4 has 36 chars (including hyphens)
        assert len(exc.trace_id) == 36

    def test_app_error_accepts_explicit_trace_id(self):
        trace = "req-test-trace-id"
        exc = AppError("error", trace_id=trace)
        assert exc.trace_id == trace

    def test_exceptions_are_subclasses_of_app_error(self):
        assert issubclass(ExtractionError, AppError)
        assert issubclass(LLMError, AppError)
        assert issubclass(ProcessingError, AppError)
        assert issubclass(PdfGenerationError, AppError)

    def test_exceptions_inherit_from_python_exception(self):
        """Ensures they can be caught by bare except Exception clauses."""
        exc = ExtractionError("test")
        assert isinstance(exc, Exception)


# ── Global Exception Handler Tests ────────────────────────────────────────────

@pytest.mark.unit
class TestGlobalExceptionHandlers:
    """Test that AppError and unhandled Exception produce the correct JSON shape."""

    def test_app_error_returns_json_with_trace_id(self, test_client):
        """A route that raises AppError should return {detail, trace_id}."""
        from app.main import app

        @app.get("/test-app-error")
        async def _trigger():
            raise ExtractionError("bad file", trace_id="test-trace-123")

        response = test_client.get("/test-app-error")
        assert response.status_code == 400
        body = response.json()
        assert body["detail"] == "bad file"
        # The middleware injects its own UUID into request.state.trace_id which
        # the handler uses in preference to exc.trace_id — so we only verify
        # that a non-empty trace_id is present.
        assert "trace_id" in body
        assert len(body["trace_id"]) == 36  # UUID v4 (8-4-4-4-12)

    def test_app_error_response_has_x_trace_id_header(self, test_client):
        """Every response should carry X-Trace-Id from the middleware."""
        response = test_client.get("/health")
        assert "x-trace-id" in response.headers

    def test_unhandled_exception_returns_500_with_trace_id(self):
        """An unhandled exception should be caught and return 500 + trace_id."""
        from app.main import app
        from fastapi.testclient import TestClient

        @app.get("/test-unhandled-error")
        async def _trigger():
            raise RuntimeError("completely unexpected")

        # raise_server_exceptions=False so TestClient returns the 500 JSONResponse
        # instead of re-raising the original exception (Starlette default behaviour).
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-unhandled-error")
        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Internal server error"
        assert "trace_id" in body


# ── Extractor Error Tests ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestExtractorErrors:
    """Test that extractor raises ExtractionError for bad inputs."""

    def test_missing_pdf_raises_extraction_error(self, tmp_path):
        from services.extractor import extract_text_from_pdf
        with pytest.raises(ExtractionError) as exc_info:
            extract_text_from_pdf(str(tmp_path / "nonexistent.pdf"))
        assert "not found" in str(exc_info.value.detail).lower()

    def test_missing_docx_raises_extraction_error(self, tmp_path):
        from services.extractor import extract_text_from_docx
        with pytest.raises(ExtractionError) as exc_info:
            extract_text_from_docx(str(tmp_path / "nonexistent.docx"))
        assert "not found" in str(exc_info.value.detail).lower()

    def test_corrupted_pdf_raises_extraction_error(self, tmp_path):
        from services.extractor import extract_text_from_pdf
        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_bytes(b"%PDF-1.4 GARBAGE DATA THAT IS NOT A REAL PDF!!!")
        with pytest.raises(ExtractionError):
            extract_text_from_pdf(str(bad_pdf))

    def test_extraction_error_preserves_original_cause(self, tmp_path):
        from services.extractor import extract_text_from_pdf
        with pytest.raises(ExtractionError) as exc_info:
            extract_text_from_pdf("/no/such/file.pdf")
        # Exception chaining should preserve the original FileNotFoundError
        assert exc_info.value.__cause__ is not None


# ── Auth Logging Tests ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestAuthLogging:
    """Verify that auth event logging never leaks passwords or hashes."""

    def test_failed_login_does_not_log_password(self, test_client, caplog):
        """Sensitive data must never appear in log output."""
        import logging
        secret = "super_secret_password_123"

        with caplog.at_level(logging.WARNING):
            test_client.post(
                "/auth/login",
                json={"email": "ghost@example.com", "password": secret}
            )

        # The raw password must never appear in any log record
        full_log = " ".join(caplog.messages)
        assert secret not in full_log, "Password leaked into log output!"

    def test_failed_login_does_not_log_full_email(self, test_client, caplog):
        """Full email addresses should not appear in logs (only domain)."""
        import logging
        email = "victim@targetdomain.com"

        with caplog.at_level(logging.WARNING):
            test_client.post(
                "/auth/login",
                json={"email": email, "password": "somepassword"}
            )

        full_log = " ".join(caplog.messages)
        # The local part of the email (before @) must not appear
        assert "victim" not in full_log, "Email local-part leaked into logs!"

    def test_successful_registration_response(self, test_client):
        """Registration response must include token and user but not password."""
        response = test_client.post(
            "/auth/register",
            json={"email": "logging_test@example.com", "password": "securepass123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "hashed_password" not in str(data)
        assert "password" not in str(data)
