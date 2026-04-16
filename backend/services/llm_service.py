import os
import json
import asyncio
from typing import AsyncGenerator, Optional
from sqlalchemy.orm import Session


class TokenCounter:
    """Accumulates token counts during a streaming response."""
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def update(self, prompt=0, completion=0, total=0):
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total

    def to_dict(self):
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


def _save_token_usage(
    db: Optional[Session],
    user_id: Optional[int],
    task_id: Optional[int],
    agent_type: Optional[str],
    provider: str,
    model_name: str,
    counter: TokenCounter,
):
    """Persist a TokenUsage record (best-effort, never raises)."""
    if not db or counter.total_tokens == 0:
        return
    try:
        from models import TokenUsage
        usage = TokenUsage(
            user_id=user_id,
            task_id=task_id,
            agent_type=agent_type,
            provider=provider,
            model_name=model_name,
            prompt_tokens=counter.prompt_tokens,
            completion_tokens=counter.completion_tokens,
            total_tokens=counter.total_tokens,
        )
        db.add(usage)
        db.commit()
    except Exception as e:
        print(f"[TokenUsage] save failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


class LLMService:
    """Supports OpenAI, Anthropic (Claude), Volcano Engine (火山引擎)"""

    async def stream_chat(
        self,
        messages: list,
        provider: str,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
        # Token tracking context (optional)
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
        task_id: Optional[int] = None,
        agent_type: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        counter = TokenCounter()

        if provider == "anthropic":
            async for chunk in self._stream_anthropic(messages, api_key, model_name, counter):
                yield chunk
        elif provider == "openai":
            async for chunk in self._stream_openai(messages, api_key, model_name, base_url, counter):
                yield chunk
        elif provider == "volcano":
            volcano_url = base_url or "https://ark.volcengineapi.com/api/v3"
            async for chunk in self._stream_openai(messages, api_key, model_name, volcano_url, counter):
                yield chunk
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Persist usage after stream completes
        _save_token_usage(db, user_id, task_id, agent_type, provider, model_name, counter)

    async def _stream_openai(
        self,
        messages: list,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
        counter: Optional[TokenCounter] = None,
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None
        )
        stream = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
            max_tokens=4096,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            # OpenAI sends usage in the final chunk when stream_options.include_usage=True
            if hasattr(chunk, 'usage') and chunk.usage and counter:
                counter.update(
                    prompt=chunk.usage.prompt_tokens or 0,
                    completion=chunk.usage.completion_tokens or 0,
                    total=chunk.usage.total_tokens or 0,
                )

    async def _stream_anthropic(
        self,
        messages: list,
        api_key: str,
        model_name: str,
        counter: Optional[TokenCounter] = None,
    ) -> AsyncGenerator[str, None]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)

        # Extract system message if present
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs = {
            "model": model_name,
            "max_tokens": 4096,
            "messages": chat_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

            # Get final message for usage stats
            response = await stream.get_final_message()
            if response and response.usage and counter:
                counter.update(
                    prompt=response.usage.input_tokens or 0,
                    completion=response.usage.output_tokens or 0,
                    total=(response.usage.input_tokens or 0) + (response.usage.output_tokens or 0),
                )

    async def complete(
        self,
        messages: list,
        provider: str,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
        # Token tracking context (optional)
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
        task_id: Optional[int] = None,
        agent_type: Optional[str] = None,
    ) -> str:
        """Non-streaming completion"""
        result = []
        async for chunk in self.stream_chat(
            messages, provider, api_key, model_name, base_url,
            db=db, user_id=user_id, task_id=task_id, agent_type=agent_type,
        ):
            result.append(chunk)
        return "".join(result)


def get_llm_config_for_agent(agent_type: str, db: Session):
    """Get the best LLM config for a given agent type"""
    from models import LLMConfig
    # Try agent-specific config first
    config = db.query(LLMConfig).filter(
        LLMConfig.agent_type == agent_type,
        LLMConfig.is_active == True
    ).first()
    if not config:
        # Fall back to "all" config
        config = db.query(LLMConfig).filter(
            LLMConfig.agent_type == "all",
            LLMConfig.is_active == True
        ).first()
    return config
