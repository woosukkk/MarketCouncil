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

        where = None
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

            where = {
                "published_timestamp": {"$lte": cutoff},
            }

        query_options = {
            "query_embeddings": query_embedding,
            "n_results": top_k,
        }
        if where:
            query_options["where"] = where

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
            retrieved_chunks.append({
                "text": document,
                "source": metadata["source"],
                "chunk_id": metadata["chunk_id"],
                "distance": distance,
                "metadata": metadata,
            })

        return retrieved_chunks


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
