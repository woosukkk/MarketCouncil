from pathlib import Path

import streamlit as st

from rag.document_loader import (
    SUPPORTED_DOCUMENT_SUFFIXES,
    load_document_text,
)
from rag.document_registry import INBOX_DIR, DocumentRegistry
from rag.ingestion_pipeline import IngestionPipeline


SOURCE_TYPES = (
    "broker_report",
    "company_ir",
    "regulatory_filing",
    "industry_report",
    "research_report",
)
REJECTION_REASONS = (
    "대상 기업과 관련 없음",
    "기존 문서와 중복",
    "출처 불명",
    "발행일 불명",
    "광고성 콘텐츠",
    "텍스트 추출 실패",
    "문서 내용 부족",
    "지나치게 오래된 자료",
    "저작권 또는 접근 권한 문제",
    "기타",
)


def save_uploaded_file(uploaded_file) -> Path:
    registry = DocumentRegistry()
    safe_name = Path(uploaded_file.name).name
    if Path(safe_name).suffix.lower() != ".pdf":
        raise ValueError("PDF 파일만 업로드할 수 있습니다.")

    destination = registry.unique_destination(INBOX_DIR, safe_name)
    destination.write_bytes(uploaded_file.getbuffer())
    return destination


def render_registration(pipeline: IngestionPipeline) -> None:
    registry = pipeline.registry
    records = registry.load()
    registered_hashes = set(records)
    unregistered_files = []

    for file_path in INBOX_DIR.iterdir():
        if (
            not file_path.is_file()
            or file_path.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES
        ):
            continue
        content_hash = registry.file_hash(file_path)
        if content_hash not in registered_hashes:
            unregistered_files.append(file_path)

    if not unregistered_files:
        st.info("메타데이터를 등록할 새 문서가 없습니다.")
        return

    selected = st.selectbox(
        "등록할 문서",
        unregistered_files,
        format_func=lambda path: path.name,
    )

    with st.form("metadata_form"):
        company = st.text_input("기업명 *")
        ticker = st.text_input("티커")
        title = st.text_input("문서 제목", value=selected.stem)
        publisher = st.text_input("발행처")
        source_type = st.selectbox("문서 유형", SOURCE_TYPES)
        source_url = st.text_input("원본 URL")
        published_at = st.date_input("발행일", value=None)
        event_date = st.date_input("사건일", value=None)
        fiscal_period = st.text_input("회계기간", placeholder="예: 2026-Q2")
        price_reference_date = st.date_input("주가 기준일", value=None)
        date_confidence = st.selectbox(
            "날짜 신뢰도",
            ("high", "medium", "low"),
            index=1,
        )
        submitted = st.form_submit_button("검토 대기열에 등록")

    if submitted:
        metadata = {
            "company": company,
            "ticker": ticker,
            "title": title,
            "publisher": publisher,
            "source_type": source_type,
            "source_url": source_url,
            "published_at": published_at.isoformat() if published_at else "",
            "event_date": event_date.isoformat() if event_date else "",
            "fiscal_period": fiscal_period,
            "price_reference_date": (
                price_reference_date.isoformat()
                if price_reference_date else ""
            ),
            "date_confidence": date_confidence,
        }
        try:
            pipeline.register_inbox_document(selected, metadata)
        except (OSError, ValueError) as error:
            st.error(str(error))
        else:
            st.success("문서를 검토 대기열에 등록했습니다.")
            st.rerun()


def render_pending_reviews(pipeline: IngestionPipeline) -> None:
    pending = [
        record
        for record in pipeline.registry.load().values()
        if record.get("status") == "pending"
    ]

    if not pending:
        st.info("검토 대기 중인 문서가 없습니다.")
        return

    selected_id = st.selectbox(
        "검토할 문서",
        [record["content_hash"] for record in pending],
        format_func=lambda content_hash: next(
            record.get("title") or record.get("filename")
            for record in pending
            if record["content_hash"] == content_hash
        ),
    )
    record = next(
        item for item in pending if item["content_hash"] == selected_id
    )
    file_path = Path(record["file_path"])

    st.json({
        key: record.get(key, "")
        for key in (
            "company",
            "ticker",
            "title",
            "publisher",
            "source_type",
            "source_url",
            "original_file_path",
            "published_at",
            "event_date",
            "fiscal_period",
            "price_reference_date",
            "date_confidence",
            "collected_at",
        )
    })

    validation = record.get("validation", {})
    for error in validation.get("errors", []):
        st.error(error)
    for warning in validation.get("warnings", []):
        st.warning(warning)

    if file_path.exists():
        with file_path.open("rb") as file:
            st.download_button(
                "검토 문서 열기 또는 다운로드",
                data=file.read(),
                file_name=file_path.name,
                mime="application/octet-stream",
            )
        try:
            preview = load_document_text(file_path)[:5000]
        except Exception as error:
            st.error(f"텍스트 미리보기 실패: {error}")
        else:
            st.text_area("추출 텍스트 미리보기", preview, height=300)

    approve_disabled = bool(validation.get("errors"))
    if st.button(
        "승인",
        disabled=approve_disabled,
        type="primary",
    ):
        try:
            pipeline.approve(selected_id)
        except (KeyError, OSError, ValueError) as error:
            st.error(str(error))
        else:
            st.success("문서를 승인했습니다. 아래 버튼으로 인덱싱하세요.")
            st.rerun()

    with st.form("reject_form"):
        rejection_reason = st.selectbox("거절 이유", REJECTION_REASONS)
        rejection_detail = st.text_input("추가 설명")
        rejected = st.form_submit_button("거절")

    if rejected:
        reason = rejection_reason
        if rejection_detail.strip():
            reason = f"{reason}: {rejection_detail.strip()}"
        try:
            pipeline.reject(selected_id, reason)
        except (KeyError, OSError, ValueError) as error:
            st.error(str(error))
        else:
            st.success("문서를 거절하고 사유를 기록했습니다.")
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="투자 문서 검토", layout="wide")
    st.title("투자 공시·리포트 검토")
    pipeline = IngestionPipeline()

    uploaded_file = st.file_uploader("PDF 업로드", type=("pdf",))
    if uploaded_file and st.button("검토 대기 폴더에 저장"):
        try:
            destination = save_uploaded_file(uploaded_file)
        except (OSError, ValueError) as error:
            st.error(str(error))
        else:
            st.success(f"저장 완료: {destination.name}")
            st.rerun()

    registration_tab, review_tab, index_tab = st.tabs((
        "메타데이터 등록",
        "승인·거절",
        "벡터 DB 반영",
    ))

    with registration_tab:
        render_registration(pipeline)
    with review_tab:
        render_pending_reviews(pipeline)
    with index_tab:
        st.write("승인된 새 문서만 증분 임베딩합니다.")
        if st.button("승인 문서 인덱싱"):
            try:
                from rag.vector_store import build_vector_store

                build_vector_store()
            except Exception as error:
                st.error(f"인덱싱 실패: {error}")
            else:
                st.success("벡터 DB 반영이 완료되었습니다.")


if __name__ == "__main__":
    main()
