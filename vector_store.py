import chromadb
from sentence_transformers import SentenceTransformer

from text_splitter import load_document_chunks


MODEL_NAME = "BAAI/bge-m3"
DB_PATH = "vector_db_bge_m3"
COLLECTION_NAME = "investment_reports_bge_m3"

def build_vector_store() -> None:
    chunks = load_document_chunks()

    model = SentenceTransformer(MODEL_NAME)

    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_or_create_collection(
    name=COLLECTION_NAME
    )

    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts).tolist()

    ids = [
        f'{chunk["source"]}_{chunk["chunk_id"]}'
        for chunk in chunks
    ]

    metadatas = [
        {
            "source": chunk["source"],
            "chunk_id": chunk["chunk_id"],
        }
        for chunk in chunks
    ]

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"벡터 DB 저장 완료: {len(chunks)}개 청크")


if __name__ == "__main__":
    build_vector_store()