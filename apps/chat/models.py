from django.db import models

from apps.core.models import TimestampedModel


class Conversation(TimestampedModel):
    """A chat conversation."""

    title = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f"Conversation {self.pk}"

    def generate_title(self):
        """Generate a title from the first user message."""
        first_message = self.messages.filter(role='user').first()
        if first_message:
            self.title = first_message.content[:50]
            if len(first_message.content) > 50:
                self.title += "..."
            self.save()


class Message(models.Model):
    """A message in a conversation."""

    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    sources = models.JSONField(
        default=list,
        help_text="List of source chunks used for this response"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}..."
