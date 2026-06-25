from openai import AsyncOpenAI
from ..config import settings


class DeepSeekClient:
    def __init__(self):
        self._client = None
        self.model = settings.deepseek_model

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = settings.deepseek_api_key
            if not api_key:
                raise ValueError(
                    "DeepSeek API key not configured. "
                    "Set DEEPSEEK_API_KEY in .env or environment variables."
                )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.deepseek_base_url,
            )
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"DeepSeek API call failed: {e}") from e


deepseek = DeepSeekClient()
