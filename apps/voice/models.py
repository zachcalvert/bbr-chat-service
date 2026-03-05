from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimestampedModel


class VoiceMember(TimestampedModel):
    """A person from the group chat corpus whose writing style can be used."""

    name = models.CharField(max_length=255, unique=True)
    message_count = models.IntegerField(default=0)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this voice is available for selection",
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.message_count} messages)"


class VoiceMessage(models.Model):
    """An individual message from the group chat corpus, embedded for style retrieval."""

    member = models.ForeignKey(
        VoiceMember,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    content = models.TextField()
    embedding = VectorField(dimensions=768)
    original_timestamp = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['member', 'original_timestamp']

    def __str__(self):
        return f"{self.member.name}: {self.content[:50]}..."
