import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-5-mini"

if not OPENAI_API_KEY:
    raise ValueError(".env 파일에 OPENAI_API_KEY를 입력하세요.")