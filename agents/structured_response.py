import json
from typing import Any

from openai import OpenAI

from config import MODEL_NAME


def create_structured_response(
    client: OpenAI,
    instructions: str,
    input_data: dict[str, Any],
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 5000,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(2):
        token_limit = max_output_tokens * (attempt + 1)
        try:
            response = client.responses.create(
                model=MODEL_NAME,
                instructions=instructions,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    }
                },
                input=json.dumps(input_data, ensure_ascii=False, default=str),
                max_output_tokens=token_limit,
            )
            status = getattr(response, "status", "completed")
            if status != "completed":
                raise ValueError(
                    f"응답 상태={status}, 상세={getattr(response, 'incomplete_details', None)}"
                )
            result = json.loads(response.output_text)
            if not isinstance(result, dict):
                raise ValueError("응답이 JSON 객체가 아닙니다.")
            return result
        except (json.JSONDecodeError, ValueError) as error:
            last_error = error
            if attempt == 0:
                continue
        except Exception as error:
            raise RuntimeError(f"구조화 분석 호출에 실패했습니다: {error}") from error
    raise RuntimeError(f"구조화 분석 응답 생성에 실패했습니다: {last_error}") from last_error
