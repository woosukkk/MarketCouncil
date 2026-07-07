from pathlib import Path

from pypdf import PdfReader


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

    for file_path in DOCUMENTS_DIR.glob("*.pdf"):
        documents[file_path.name] = load_pdf_text(file_path)

    return documents


if __name__ == "__main__":
    documents = load_all_documents()

    for filename, text in documents.items():
        print(f"\n===== {filename} =====")
        print(text[:2000])