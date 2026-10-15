import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import chromadb
from chromadb.config import Settings
from rag.retriever import ReportRetriever

class HistoricalRetrievalTests(unittest.TestCase):
    def test_filter_precedes_top_k_with_real_chroma_and_no_embedding_download(self) -> None:
        import uuid
        client=chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        collection=client.create_collection("audit_"+uuid.uuid4().hex)
        stamp=lambda text:int(datetime.fromisoformat(text).replace(tzinfo=timezone(timedelta(hours=9))).timestamp())
        rows=[("future"+str(i),"삼성전자",stamp("2026-12-01"),[1.,0.]) for i in range(9)]
        rows += [("past","삼성전자",stamp("2026-01-01"),[.8,.2]),("undated","삼성전자",0,[1.,0.]),("other","다른기업",stamp("2026-01-01"),[1.,0.])]
        collection.add(ids=[r[0] for r in rows],documents=[r[0] for r in rows],embeddings=[r[3] for r in rows],metadatas=[{"source":r[0],"chunk_id":0,"company":r[1],"published_timestamp":r[2]} for r in rows])
        fake=MagicMock();fake.get_or_create_collection.return_value=collection
        try:
            with patch("rag.retriever.get_chroma_client",return_value=fake):
                retriever=ReportRetriever();retriever.model=MagicMock()
                retriever.model.encode.return_value.tolist.return_value=[[1.,0.]]
                results=retriever.search("query",top_k=3,company_name="삼성전자",as_of_date="2026-10-15")
            self.assertEqual([r["source"] for r in results],["past"])
        finally:client.delete_collection(collection.name)

    def test_invalid_date_and_top_k_fail_before_model_or_query(self) -> None:
        with patch("rag.retriever.get_chroma_client") as factory:
            retriever=ReportRetriever();retriever.model=MagicMock()
            for options in [{"top_k":0},{"top_k":True},{"as_of_date":"wrong"}]:
                with self.assertRaises(ValueError):retriever.search("query",**options)
            retriever.model.encode.assert_not_called()
            retriever.collection.query.assert_not_called()

if __name__=="__main__":unittest.main()
