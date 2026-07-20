from pathlib import Path

from pypdf import PdfReader

from rag.document_registry import APPROVED_DIR


DOCUMENTS_DIR = Path("documents")


def load_pdf_text(file_path: Path) -> str:
    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


def load_all_documents() -> dict[str, str]:
    documents = {}

    file_paths = [
        *DOCUMENTS_DIR.glob("*.pdf"),
        *APPROVED_DIR.glob("*.pdf"),
    ]

    for file_path in file_paths:
        documents[file_path.name] = load_pdf_text(file_path)

    return documents


if __name__ == "__main__":
    documents = load_all_documents()

    for filename, text in documents.items():
        print(f"\n===== {filename} =====")
        print(text[:2000])
