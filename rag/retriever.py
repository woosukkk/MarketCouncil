import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

MODEL_NAME = "BAAI/bge-m3"
DB_PATH = "vector_db_bge_m3"
COLLECTION_NAME = "investment_reports_bge_m3"

class ReportRetriever:
    def __init__(self) -> None:
        self.model = SentenceTransformer(MODEL_NAME)

        self.client = chromadb.PersistentClient(
            path=DB_PATH
            )

        self.collection = self.client.get_collection(
            name=COLLECTION_NAME
            )

    def search(
        self,
        query: str,
        top_k: int = 3,
        as_of_date: str | None = None,
    ) -> list[dict]:
        query_embedding = self.model.encode(
            [query]
        ).tolist()

        cutoff = int(datetime.now().timestamp())
        if as_of_date:
            try:
                cutoff_text = as_of_date
                if len(as_of_date) == 10:
                    cutoff_text = f"{as_of_date}T23:59:59"
                cutoff = int(datetime.fromisoformat(cutoff_text).timestamp())
            except ValueError as error:
                raise ValueError(
                    "as_of_date는 ISO 날짜 형식이어야 합니다."
                ) from error

        query_options = {
            "query_embeddings": query_embedding,
            "n_results": max(top_k * 3, top_k),
        }

        results = self.collection.query(
            **query_options,
        )

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        retrieved_chunks = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            published_timestamp = int(
                metadata.get("published_timestamp", 0) or 0
            )
            if published_timestamp > cutoff:
                continue

            age_days = None
            recency_penalty = 0.1
            if published_timestamp:
                age_days = max(
                    0,
                    (cutoff - published_timestamp) // 86400,
                )
                if age_days <= 30:
                    recency_penalty = 0.0
                elif age_days <= 90:
                    recency_penalty = 0.03
                elif age_days <= 365:
                    recency_penalty = 0.08
                else:
                    recency_penalty = 0.15

            retrieved_chunks.append({
                "text": document,
                "source": metadata["source"],
                "chunk_id": metadata["chunk_id"],
                "distance": distance,
                "ranking_score": float(distance) + recency_penalty,
                "age_days": age_days,
                "metadata": metadata,
            })

        return sorted(
            retrieved_chunks,
            key=lambda chunk: chunk["ranking_score"],
        )[:top_k]


if __name__ == "__main__":
    retriever = ReportRetriever()

    query = "삼성전자의 긍정적인 성장 요인은 무엇인가?"

    results = retriever.search(
        query=query,
        top_k=3,
    )

    for result in results:
        print("\n====================")
        print(f'출처: {result["source"]}')
        print(f'청크 번호: {result["chunk_id"]}')
        print(f'거리: {result["distance"]}')
        print(result["text"][:1000])
