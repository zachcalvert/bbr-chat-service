import logging
from typing import Generator

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for chat (Groq) and embeddings (OpenAI)."""

    def __init__(self):
        self.chat_client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        self.embed_client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
        )
        self.chat_model = settings.CHAT_MODEL
        self.embed_model = settings.EMBED_MODEL
        self.embed_dimensions = settings.EMBED_DIMENSIONS

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        system: str | None = None,
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Override the default chat model
            system: System prompt to prepend
            stream: Whether to stream the response

        Returns:
            Complete response text or generator of chunks if streaming
        """
        model = model or self.chat_model

        if system:
            messages = [{"role": "system", "content": system}] + messages

        if stream:
            return self._stream_chat(messages, model)
        else:
            return self._sync_chat(messages, model)

    def _sync_chat(self, messages: list[dict], model: str) -> str:
        """Synchronous chat request."""
        try:
            response = self.chat_client.chat.completions.create(
                model=model,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise

    def _stream_chat(self, messages: list[dict], model: str) -> Generator[str, None, None]:
        """Streaming chat request."""
        try:
            stream = self.chat_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            raise

    def embed(self, text: str | list[str], model: str | None = None) -> list[list[float]]:
        """
        Generate embeddings for text(s).

        Args:
            text: Single text or list of texts to embed
            model: Override the default embedding model

        Returns:
            List of embedding vectors
        """
        model = model or self.embed_model

        if isinstance(text, str):
            text = [text]

        try:
            response = self.embed_client.embeddings.create(
                model=model,
                input=text,
                dimensions=self.embed_dimensions,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Embed error: {e}")
            raise

    def embed_single(self, text: str, model: str | None = None) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = self.embed(text, model)
        return embeddings[0] if embeddings else []


# Default client instance
llm_client = LLMClient()
