"""Voice translation pipeline — rewrites RAG responses in a specific person's style."""
import logging
from dataclasses import dataclass
from typing import Generator

from django.conf import settings
from pgvector.django import L2Distance

from apps.core.llm_client import llm_client
from apps.voice.models import VoiceMember, VoiceMessage

logger = logging.getLogger(__name__)


@dataclass
class VoiceExample:
    """A retrieved voice message used as a style example."""
    content: str
    member_name: str
    distance: float


class VoiceTranslator:
    """Translates factual RAG responses into a specific person's writing voice."""

    def __init__(self, num_examples: int | None = None):
        self.num_examples = num_examples or settings.VOICE_NUM_EXAMPLES

    def retrieve_examples(
        self,
        text: str,
        member: VoiceMember | None = None,
        blend: bool = False,
    ) -> list[VoiceExample]:
        """
        Retrieve voice message examples similar to the given text.

        Uses the RAG response as the query to find stylistically
        relevant messages from the target voice member.
        """
        query_embedding = llm_client.embed_single(text)

        if not query_embedding:
            logger.warning("Failed to embed text for voice retrieval")
            return []

        queryset = VoiceMessage.objects.annotate(
            distance=L2Distance('embedding', query_embedding)
        )

        if not blend and member:
            queryset = queryset.filter(member=member)
        else:
            queryset = queryset.filter(member__is_active=True)

        results = queryset.order_by('distance')[:self.num_examples]

        return [
            VoiceExample(
                content=msg.content,
                member_name=msg.member.name,
                distance=msg.distance,
            )
            for msg in results.select_related('member')
        ]

    def build_translation_prompt(
        self,
        rag_response: str,
        examples: list[VoiceExample],
        member: VoiceMember | None = None,
        blend: bool = False,
    ) -> tuple[str, list[dict]]:
        """Build the system prompt and messages for the translation LLM call."""
        if blend:
            voice_desc = "the group chat"
            name_label = "the group"
        else:
            voice_desc = member.name if member else "the selected person"
            name_label = member.name if member else "them"

        examples_block = ""
        for i, ex in enumerate(examples, 1):
            if blend:
                examples_block += f"[{ex.member_name}]: {ex.content}\n"
            else:
                examples_block += f"Example {i}: {ex.content}\n"

        system_prompt = (
            f"You are a writing style translator. Your job is to rewrite factual information "
            f"in the voice and writing style of {voice_desc}.\n\n"
            f"Rules:\n"
            f"- Preserve ALL factual information from the original response. Do not omit, change, or add facts.\n"
            f"- Adopt the tone, vocabulary, sentence structure, slang, humor, and mannerisms shown in the examples.\n"
            f"- Keep the response roughly the same length as the original.\n"
            f"- Do not mention that you are translating or rewriting.\n"
            f"- Do not add disclaimers about the style transfer.\n"
            f"- If the examples use casual language, abbreviations, or specific phrases, mirror those patterns.\n"
            f"- The result should read as if {name_label} wrote it naturally."
        )

        user_message = (
            f"Here are examples of how {voice_desc} writes:\n\n"
            f"{examples_block}\n"
            f"---\n\n"
            f"Now rewrite the following factual response in that same voice and style:\n\n"
            f"{rag_response}"
        )

        messages = [{"role": "user", "content": user_message}]
        return system_prompt, messages

    def translate(
        self,
        rag_response: str,
        member: VoiceMember | None = None,
        blend: bool = False,
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """
        Translate a RAG response into the target voice.

        Returns the original response unchanged if no voice is selected.
        """
        if not member and not blend:
            if stream:
                def passthrough():
                    yield rag_response
                return passthrough()
            return rag_response

        examples = self.retrieve_examples(
            text=rag_response,
            member=member,
            blend=blend,
        )

        if not examples:
            logger.warning("No voice examples found, returning original response")
            if stream:
                def passthrough():
                    yield rag_response
                return passthrough()
            return rag_response

        system_prompt, messages = self.build_translation_prompt(
            rag_response=rag_response,
            examples=examples,
            member=member,
            blend=blend,
        )

        return llm_client.chat(
            messages=messages,
            system=system_prompt,
            stream=stream,
        )


voice_translator = VoiceTranslator()
