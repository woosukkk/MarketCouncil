import os
from typing import Any

import chromadb
from dotenv import load_dotenv

load_dotenv()


def get_chroma_client() -> Any:
    mode = os.getenv("CHROMA_MODE", "local")
    if mode == "local":
        return chromadb.PersistentClient(path="vector_db_bge_m3")
    if mode != "cloud":
        raise ValueError("CHROMA_MODE must be local or cloud")
    names = ("CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE")
    if any(not os.getenv(name) for name in names):
        raise ValueError("Chroma Cloud credentials are incomplete")
    return chromadb.CloudClient(api_key=os.environ[names[0]],
                               tenant=os.environ[names[1]], database=os.environ[names[2]])
