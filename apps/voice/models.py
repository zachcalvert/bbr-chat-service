from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimestampedModel


class VoiceMember(TimestampedModel):
    """A person from the group chat corpus whose writing style can be used."""

    name = models.CharField(max_length=255, unique=True, help_text="GroupMe user ID — do not edit")
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Friendly name shown in the UI (e.g. 'Zach'). Falls back to name if blank.",
    )
    message_count = models.IntegerField(default=0)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this voice is available for selection",
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        label = self.display_name or self.name
        return f"{label} ({self.message_count} messages)"

    @property
    def label(self):
        """Display name if set, otherwise falls back to the raw name."""
        return self.display_name or self.name


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
