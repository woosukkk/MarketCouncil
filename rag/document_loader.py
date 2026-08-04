import html
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

from rag.document_registry import APPROVED_DIR


DOCUMENTS_DIR = Path("documents")
SUPPORTED_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".txt",
    ".html",
    ".htm",
    ".xml",
    ".xhtml",
    ".zip",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return "\n".join(self.parts)


def load_pdf_text(file_path: Path) -> str:
    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


def load_document_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf_text(file_path)
    if suffix == ".zip":
        return _load_zip_text(file_path)
    if suffix in {".txt", ".html", ".htm", ".xml", ".xhtml"}:
        value = _decode_bytes(file_path.read_bytes())
        return value if suffix == ".txt" else _strip_markup(value)
    raise ValueError(f"지원하지 않는 문서 형식입니다: {suffix or '확장자 없음'}")


def _load_zip_text(file_path: Path) -> str:
    parts: list[str] = []
    try:
        with zipfile.ZipFile(file_path) as archive:
            for name in sorted(archive.namelist()):
                suffix = Path(name).suffix.lower()
                if suffix not in {".txt", ".html", ".htm", ".xml", ".xhtml"}:
                    continue
                value = _decode_bytes(archive.read(name))
                text = value if suffix == ".txt" else _strip_markup(value)
                if text.strip():
                    parts.append(text)
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError(f"ZIP 문서를 읽을 수 없습니다: {file_path.name}") from error
    return "\n\n".join(parts)


def _decode_bytes(value: bytes) -> str:
    for encoding in ("utf-8", "euc-kr", "cp949"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _strip_markup(value: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html.unescape(value))
    except Exception as error:
        raise ValueError("HTML/XML 본문을 추출할 수 없습니다.") from error
    return parser.text()


def load_all_documents() -> dict[str, str]:
    documents = {}

    file_paths = [
        *DOCUMENTS_DIR.glob("*.pdf"),
        *(
            path
            for path in APPROVED_DIR.glob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES
        ),
    ]

    for file_path in file_paths:
        documents[file_path.name] = load_document_text(file_path)

    return documents


if __name__ == "__main__":
    documents = load_all_documents()

    for filename, text in documents.items():
        print(f"\n===== {filename} =====")
        print(text[:2000])
