from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimestampedModel


class KnowledgeEntry(TimestampedModel):
    """A piece of knowledge content added by the user."""

    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.CharField(max_length=100, blank=True)
    source_url = models.URLField(blank=True)

    class Meta:
        verbose_name_plural = "Knowledge entries"
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class KnowledgeChunk(models.Model):
    """An embedded chunk of a knowledge entry for vector search."""

    entry = models.ForeignKey(
        KnowledgeEntry,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    content = models.TextField()
    embedding = VectorField(dimensions=768)
    chunk_index = models.IntegerField()

    class Meta:
        ordering = ['entry', 'chunk_index']
        unique_together = ['entry', 'chunk_index']

    def __str__(self):
        return f"{self.entry.title} - Chunk {self.chunk_index}"
