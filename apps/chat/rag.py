"""RAG (Retrieval-Augmented Generation) pipeline."""
import logging
from dataclasses import dataclass
from typing import Generator

from django.conf import settings
from pgvector.django import L2Distance

from apps.core.llm_client import llm_client
from apps.crawler.models import CrawledChunk
from apps.knowledge.models import KnowledgeChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A chunk retrieved from vector search."""
    content: str
    source_type: str  # 'knowledge' or 'crawled'
    source_title: str
    source_url: str | None
    distance: float


class RAGPipeline:
    """RAG pipeline for question answering."""

    def __init__(
        self,
        top_k: int | None = None,
        chat_model: str | None = None,
    ):
        self.top_k = top_k or settings.RAG_TOP_K
        self.chat_model = chat_model or settings.CHAT_MODEL

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: The user's question

        Returns:
            List of relevant chunks with metadata
        """
        # Get query embedding
        query_embedding = llm_client.embed_single(query)

        if not query_embedding:
            logger.warning("Failed to embed query")
            return []

        retrieved = []

        # Search knowledge chunks
        knowledge_chunks = (
            KnowledgeChunk.objects
            .annotate(distance=L2Distance('embedding', query_embedding))
            .order_by('distance')
            [:self.top_k]
        )

        for chunk in knowledge_chunks:
            retrieved.append(RetrievedChunk(
                content=chunk.content,
                source_type='knowledge',
                source_title=chunk.entry.title,
                source_url=chunk.entry.source_url or None,
                distance=chunk.distance,
            ))

        # Search crawled chunks
        crawled_chunks = (
            CrawledChunk.objects
            .select_related('page')
            .annotate(distance=L2Distance('embedding', query_embedding))
            .order_by('distance')
            [:self.top_k]
        )

        for chunk in crawled_chunks:
            retrieved.append(RetrievedChunk(
                content=chunk.content,
                source_type='crawled',
                source_title=chunk.page.title or "Web Page",
                source_url=chunk.page.url,
                distance=chunk.distance,
            ))

        # Sort by distance and take top_k overall
        retrieved.sort(key=lambda x: x.distance)
        return retrieved[:self.top_k]

    def build_context(self, chunks: list[RetrievedChunk]) -> str:
        """Build context string from retrieved chunks."""
        if not chunks:
            return "No relevant context found."

        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source_info = f"[Source {i}: {chunk.source_title}]"
            context_parts.append(f"{source_info}\n{chunk.content}")

        return "\n\n---\n\n".join(context_parts)

    def generate(
        self,
        query: str,
        context: str,
        conversation_history: list[dict] | None = None,
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """
        Generate a response using the LLM.

        Args:
            query: The user's question
            context: Retrieved context
            conversation_history: Previous messages in the conversation
            stream: Whether to stream the response

        Returns:
            Generated response or generator if streaming
        """
        system_prompt = """You are a helpful AI assistant for a business incubator.
You answer questions using the provided context from the knowledge base and crawled web content.

Guidelines:
- Base your answers on the provided context
- If the context doesn't contain relevant information, say so
- Be concise but thorough
- When citing information, mention the source
- If asked about topics not in the context, provide general guidance but note that specific information wasn't found"""

        # Build messages
        messages = []

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history[-6:])  # Keep last 3 exchanges

        # Add current query with context
        user_message = f"""Context:
{context}

Question: {query}

Please answer the question based on the context provided above."""

        messages.append({"role": "user", "content": user_message})

        return llm_client.chat(
            messages=messages,
            system=system_prompt,
            stream=stream,
        )

    def query(
        self,
        question: str,
        conversation_history: list[dict] | None = None,
        stream: bool = False,
    ) -> tuple[str | Generator[str, None, None], list[RetrievedChunk]]:
        """
        Complete RAG query: retrieve and generate.

        Args:
            question: The user's question
            conversation_history: Previous messages
            stream: Whether to stream the response

        Returns:
            Tuple of (response, retrieved_chunks)
        """
        # Retrieve relevant chunks
        chunks = self.retrieve(question)

        # Build context
        context = self.build_context(chunks)

        # Generate response
        response = self.generate(
            query=question,
            context=context,
            conversation_history=conversation_history,
            stream=stream,
        )

        return response, chunks


# Default pipeline instance
rag_pipeline = RAGPipeline()
