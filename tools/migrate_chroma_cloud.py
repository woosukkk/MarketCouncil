"""Copy a stopped local BGE-M3 collection to an empty cloud collection."""
import os

import chromadb
from dotenv import load_dotenv

from rag.chroma_client import get_chroma_client


def main() -> None:
    load_dotenv(".env.production", override=True)
    os.environ["CHROMA_MODE"] = "cloud"
    name = "investment_reports_bge_m3"
    source = chromadb.PersistentClient(path="vector_db_bge_m3").get_collection(name)
    destination = get_chroma_client().get_or_create_collection(
        name, metadata=source.metadata, embedding_function=None
    )
    if destination.count():
        raise RuntimeError("Destination must be empty; use a new database for migration")
    count = source.count()
    for offset in range(0, count, 100):
        batch = source.get(limit=100, offset=offset, include=["documents", "metadatas", "embeddings"])
        destination.add(**{key: batch[key] for key in ("ids", "documents", "metadatas", "embeddings")
                           if batch[key] is not None})
    if destination.count() != count:
        raise RuntimeError("Migration count mismatch")
    print(f"Copied and counted {count} records. Keep the local database as backup.")


if __name__ == "__main__":
    main()
