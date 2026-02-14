import logging
from typing import Generator

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(
        self,
        base_url: str | None = None,
        chat_model: str | None = None,
        embed_model: str | None = None,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.chat_model = chat_model or settings.OLLAMA_CHAT_MODEL
        self.embed_model = embed_model or settings.OLLAMA_EMBED_MODEL
        self.timeout = httpx.Timeout(120.0, connect=10.0)

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        system: str | None = None,
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """
        Send a chat completion request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Override the default chat model
            system: System prompt to prepend
            stream: Whether to stream the response

        Returns:
            Complete response text or generator of chunks if streaming
        """
        model = model or self.chat_model
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if system:
            payload["messages"] = [{"role": "system", "content": system}] + messages

        if stream:
            return self._stream_chat(url, payload)
        else:
            return self._sync_chat(url, payload)

    def _sync_chat(self, url: str, payload: dict) -> str:
        """Synchronous chat request."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    def _stream_chat(self, url: str, payload: dict) -> Generator[str, None, None]:
        """Streaming chat request."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line:
                            import json
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
        except httpx.HTTPError as e:
            logger.error(f"Ollama stream error: {e}")
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
        url = f"{self.base_url}/api/embed"

        if isinstance(text, str):
            text = [text]

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    json={"model": model, "input": text},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embeddings", [])
        except httpx.HTTPError as e:
            logger.error(f"Ollama embed error: {e}")
            raise

    def embed_single(self, text: str, model: str | None = None) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = self.embed(text, model)
        return embeddings[0] if embeddings else []

    def list_models(self) -> list[dict]:
        """List available models."""
        url = f"{self.base_url}/api/tags"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])
        except httpx.HTTPError as e:
            logger.error(f"Ollama list models error: {e}")
            return []

    def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama registry."""
        url = f"{self.base_url}/api/pull"
        try:
            with httpx.Client(timeout=httpx.Timeout(600.0)) as client:
                response = client.post(url, json={"name": model})
                response.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error(f"Ollama pull model error: {e}")
            return False

    def is_healthy(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
                response = client.get(self.base_url)
                return response.status_code == 200
        except httpx.HTTPError:
            return False


# Default client instance
ollama_client = OllamaClient()
