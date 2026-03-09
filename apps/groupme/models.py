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
