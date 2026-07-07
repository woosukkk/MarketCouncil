from rag.document_loader import load_all_documents

def split_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def load_document_chunks() -> list[dict]:
    documents = load_all_documents()
    all_chunks = []

    for filename, text in documents.items():
        chunks = split_text(text)

        for index, chunk in enumerate(chunks):
            all_chunks.append({
                "source": filename,
                "chunk_id": index,
                "text": chunk,
            })

    return all_chunks


if __name__ == "__main__":
    chunks = load_document_chunks()

    print(f"전체 청크 수: {len(chunks)}")

    for chunk in chunks[:3]:
        print("\n", chunk)