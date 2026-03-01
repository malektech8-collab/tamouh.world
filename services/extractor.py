import pdfplumber
from docx import Document
from loguru import logger

from app.exceptions import ExtractionError


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract plain text from a PDF file using pdfplumber.

    Raises:
        ExtractionError: If the file cannot be opened or parsed.
    """
    try:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        result = text.strip()
        logger.debug("PDF extracted", file_path=file_path, chars=len(result))
        return result
    except FileNotFoundError as e:
        raise ExtractionError(f"Resume file not found: {file_path}") from e
    except Exception as e:
        raise ExtractionError(f"PDF extraction failed: {e}") from e


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract plain text from a DOCX file using python-docx.

    Raises:
        ExtractionError: If the file cannot be opened or parsed.
    """
    try:
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        result = text.strip()
        logger.debug("DOCX extracted", file_path=file_path, chars=len(result))
        return result
    except FileNotFoundError as e:
        raise ExtractionError(f"Resume file not found: {file_path}") from e
    except Exception as e:
        raise ExtractionError(f"DOCX extraction failed: {e}") from e
