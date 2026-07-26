import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DART_API_KEY = os.getenv("DART_API_KEY")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT")
MODEL_NAME = "gpt-5-mini"

if not OPENAI_API_KEY:
    raise ValueError(".env 파일에 OPENAI_API_KEY를 입력하세요.")
