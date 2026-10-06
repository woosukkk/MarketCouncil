import hmac
import os

from dotenv import load_dotenv

load_dotenv()


def analysis_allowed(token: str = "") -> bool:
    mode = os.getenv("MARKETCOUNCIL_MODE", "local")
    if mode == "local":
        return True
    expected = os.getenv("ADMIN_TOKEN", "")
    return mode == "public" and len(expected) >= 32 and hmac.compare_digest(
        token.encode("utf-8"), expected.encode("utf-8")
    )
