"""v0.5 LLM 客户端——OpenAI 兼容 HTTP 接口。

支持 OpenAI / DeepSeek / Moonshot 等兼容 OpenAI Chat Completions API 的供应商。
5 秒超时降级，不阻塞主流程。
"""
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用异常。"""


class LLMClient:
    """OpenAI 兼容的 LLM 客户端。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: int = 5,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def chat_json(
        self,
        system_prompt: str,
        user_content: str,
    ) -> dict[str, Any]:
        """调用 LLM 并返回 JSON 格式响应。

        失败/超时时抛出 LLMError，由调用方降级处理。
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
        except httpx.TimeoutException:
            raise LLMError(f"LLM 调用超时（{self._timeout}s）")
        except httpx.HTTPStatusError as e:
            body = e.response.text[:200] if e.response else ""
            raise LLMError(f"LLM HTTP {e.response.status_code}: {body}")
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise LLMError(f"LLM 响应解析失败: {e}")
        except Exception as e:
            raise LLMError(f"LLM 调用失败: {e}")
