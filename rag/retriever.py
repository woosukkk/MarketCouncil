from rag.chroma_client import get_chroma_client
from sentence_transformers import SentenceTransformer
from datetime import datetime

MODEL_NAME = "BAAI/bge-m3"
DB_PATH = "vector_db_bge_m3"
COLLECTION_NAME = "investment_reports_bge_m3"

class ReportRetriever:
    def __init__(self) -> None:
        self.model = SentenceTransformer(MODEL_NAME)

        self.client = get_chroma_client()

        self.collection = self.client.get_collection(
            name=COLLECTION_NAME
            )

    def search(
        self,
        query: str,
        top_k: int = 3,
        as_of_date: str | None = None,
        source_types: set[str] | None = None,
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
        if source_types:
            sorted_types = sorted(source_types)
            query_options["where"] = (
                {"source_type": sorted_types[0]}
                if len(sorted_types) == 1
                else {"source_type": {"$in": sorted_types}}
            )

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
            recency_penalty = 0.4
            if published_timestamp:
                age_days = max(
                    0,
                    (cutoff - published_timestamp) // 86400,
                )
                if age_days <= 3:
                    recency_penalty = 0.0
                elif age_days <= 7:
                    recency_penalty = 0.01
                elif age_days <= 14:
                    recency_penalty = 0.03
                elif age_days <= 30:
                    recency_penalty = 0.06
                elif age_days <= 90:
                    recency_penalty = 0.15
                elif age_days <= 365:
                    recency_penalty = 0.3
                else:
                    recency_penalty = 0.6

            filing_penalty = self._filing_priority_penalty(metadata)

            retrieved_chunks.append({
                "text": document,
                "source": metadata["source"],
                "chunk_id": metadata["chunk_id"],
                "distance": distance,
                "ranking_score": (
                    float(distance) + recency_penalty + filing_penalty
                ),
                "age_days": age_days,
                "recency_penalty": recency_penalty,
                "filing_priority_penalty": filing_penalty,
                "metadata": metadata,
            })

        return sorted(
            retrieved_chunks,
            key=lambda chunk: chunk["ranking_score"],
        )[:top_k]

    @staticmethod
    def _filing_priority_penalty(metadata: dict) -> float:
        if metadata.get("source_type") != "regulatory_filing":
            return 0.0

        form_type = str(metadata.get("form_type", "")).upper()
        current_filing_markers = (
            "8-K",
            "6-K",
            "주요사항",
            "잠정",
            "영업(잠정)",
        )
        if any(marker in form_type for marker in current_filing_markers):
            return 0.0
        if "10-Q" in form_type or "분기보고서" in form_type:
            return 0.03
        if "반기보고서" in form_type:
            return 0.05
        if any(
            marker in form_type
            for marker in ("10-K", "20-F", "40-F", "사업보고서")
        ):
            return 0.1
        return 0.06


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
