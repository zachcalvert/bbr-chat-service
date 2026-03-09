from django.db import models

from apps.core.models import TimestampedModel


class GroupMeBot(TimestampedModel):
    """Configuration for a GroupMe bot that responds to mentions."""

    name = models.CharField(
        max_length=100,
        help_text="Trigger word to detect in messages (e.g. 'bbr'). Case-insensitive.",
    )
    bot_id = models.CharField(
        max_length=255,
        help_text="GroupMe bot ID used for posting responses.",
    )
    group_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="GroupMe group ID (for reference).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this bot responds to messages.",
    )
    voice = models.ForeignKey(
        'voice.VoiceMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='groupme_bots',
        help_text="Voice style for responses. Leave blank for plain RAG.",
    )
    voice_blend = models.BooleanField(
        default=False,
        help_text="If True, blend all active voices instead of a specific member.",
    )

    class Meta:
        verbose_name = 'GroupMe Bot'
        verbose_name_plural = 'GroupMe Bots'

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.name} ({status})"


class CallbackLog(models.Model):
    """Log of every request to the GroupMe callback endpoint."""

    class Outcome(models.TextChoices):
        IGNORED = 'ignored', 'Ignored'          # bot message, no mention, empty text
        RESPONDED = 'responded', 'Responded'     # RAG ran and response posted
        ERROR = 'error', 'Error'                 # exception during RAG or posting

    # Request data
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(
        help_text="Raw JSON body from the GroupMe callback.",
    )
    sender_type = models.CharField(max_length=50, blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    sender_id = models.CharField(max_length=255, blank=True)
    message_text = models.TextField(blank=True)

    # Processing result
    bot = models.ForeignKey(
        GroupMeBot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='callback_logs',
        help_text="Bot that handled this request, if any.",
    )
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.IGNORED,
    )
    response_text = models.TextField(
        blank=True,
        help_text="Response sent back to GroupMe, if any.",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error details if something went wrong.",
    )
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Processing time in milliseconds.",
    )

    class Meta:
        verbose_name = 'Callback Log'
        verbose_name_plural = 'Callback Logs'
        ordering = ['-received_at']

    def __str__(self):
        sender = self.sender_name or self.sender_type or "unknown"
        return f"{self.received_at:%Y-%m-%d %H:%M} — {sender} — {self.outcome}"
