from pathlib import Path
from typing import Any

from rag.document_loader import load_pdf_text


def validate_document(
    file_path: Path,
    metadata: dict[str, Any],
) -> dict[str, list[str] | int]:
    errors: list[str] = []
    warnings: list[str] = []

    if file_path.suffix.lower() != ".pdf":
        errors.append("PDF 파일만 지원합니다.")

    try:
        text = load_pdf_text(file_path)
    except Exception as error:
        errors.append(f"PDF 텍스트 추출 실패: {error}")
        text = ""

    text_length = len(text.strip())
    if text_length < 200:
        errors.append("추출된 텍스트가 200자 미만입니다. OCR이 필요할 수 있습니다.")

    company = str(metadata.get("company", "")).strip()
    if not company:
        errors.append("대상 기업명이 필요합니다.")
    elif company.lower() not in text.lower():
        warnings.append("본문에서 대상 기업명을 찾지 못했습니다.")

    if not str(metadata.get("published_at", "")).strip():
        warnings.append("발행일이 없어 최신성 평가의 신뢰도가 낮아집니다.")

    if not str(metadata.get("source_url", "")).strip():
        warnings.append("원본 URL이 없습니다.")

    return {
        "errors": errors,
        "warnings": warnings,
        "text_length": text_length,
    }
