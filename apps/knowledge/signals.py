"""Signals for knowledge app."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.llm_client import llm_client
from apps.core.text_processing import chunk_text

from .models import KnowledgeChunk, KnowledgeEntry

logger = logging.getLogger(__name__)


@receiver(post_save, sender=KnowledgeEntry)
def process_knowledge_entry(sender, instance, created, **kwargs):
    """
    Process a knowledge entry after save: chunk and embed content.

    This runs whenever a KnowledgeEntry is saved (via admin, views, or shell).
    """
    # Check if we need to re-process (content changed or no chunks exist)
    existing_chunks = instance.chunks.count()

    # Skip if this is triggered during chunk creation to avoid recursion
    if getattr(instance, '_skip_signal', False):
        return

    # For updates, we could check if content changed, but for simplicity
    # we'll re-process if there are no chunks or if explicitly requested
    if existing_chunks > 0 and not created:
        # Check if content hash changed (simple approach: compare chunk count)
        # For a production system, you'd store a content hash
        logger.info(f"Entry {instance.pk} already has {existing_chunks} chunks, skipping re-embedding")
        return

    logger.info(f"Processing knowledge entry {instance.pk}: '{instance.title}'")

    try:
        # Delete existing chunks if any
        instance.chunks.all().delete()

        chunks_to_create = []
        chunk_texts = []

        for chunk_index, chunk_content in chunk_text(instance.content):
            chunk_texts.append(chunk_content)
            chunks_to_create.append({
                'entry': instance,
                'content': chunk_content,
                'chunk_index': chunk_index,
            })

        if not chunk_texts:
            logger.warning(f"No chunks generated for entry {instance.pk}")
            return

        logger.info(f"Generating embeddings for {len(chunk_texts)} chunks")

        # Get embeddings for all chunks
        embeddings = llm_client.embed(chunk_texts)

        if not embeddings:
            logger.error(f"No embeddings returned for entry {instance.pk}")
            return

        if len(embeddings) != len(chunk_texts):
            logger.error(
                f"Embedding count mismatch: got {len(embeddings)}, expected {len(chunk_texts)}"
            )
            return

        # Create chunk objects with embeddings
        for chunk_data, embedding in zip(chunks_to_create, embeddings):
            KnowledgeChunk.objects.create(
                entry=chunk_data['entry'],
                content=chunk_data['content'],
                chunk_index=chunk_data['chunk_index'],
                embedding=embedding,
            )

        logger.info(f"Created {len(chunks_to_create)} chunks for entry {instance.pk}")

    except Exception as e:
        logger.error(f"Error processing entry {instance.pk}: {e}", exc_info=True)
        # Don't re-raise - we don't want to break the save operation
