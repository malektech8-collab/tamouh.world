"""
Custom exception hierarchy for the AI Resume SaaS Engine.

All application exceptions inherit from AppError, which carries an HTTP
status code and an optional trace ID so callers can correlate log entries
with API error responses.
"""

import uuid


class AppError(Exception):
    """
    Base application exception.

    Attributes:
        detail:      Human-readable error description (safe to return in API).
        status_code: HTTP status code for the global exception handler.
        trace_id:    Correlation ID linking this error to a specific request
                     or background job. Auto-generated if not provided.
    """
    status_code: int = 500

    def __init__(self, detail: str, trace_id: str = None):
        super().__init__(detail)
        self.detail = detail
        self.trace_id = trace_id or str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(detail={self.detail!r}, trace_id={self.trace_id!r})"


class ExtractionError(AppError):
    """
    Failed to extract text from an uploaded resume file.

    Raised by services/extractor.py when pdfplumber or python-docx cannot
    read the file (missing file, corrupted content, permission error, etc.).

    HTTP 400 — the uploaded document is the problem, not the server.
    """
    status_code = 400


class LLMError(AppError):
    """
    Error communicating with the upstream LLM API (OpenAI).

    Raised by services/parser.py when all retry attempts are exhausted or
    when the API returns an unexpected response.

    HTTP 502 — the upstream service is the problem.
    """
    status_code = 502


class ProcessingError(AppError):
    """
    General error during resume processing pipeline.

    Raised when classification, optimization, or matching steps fail in a
    way that is not attributable to the input file or the LLM API.

    HTTP 500 — internal server error.
    """
    status_code = 500


class PdfGenerationError(AppError):
    """
    Failed to render the processed resume to PDF via Playwright.

    HTTP 500 — internal server error.
    """
    status_code = 500
