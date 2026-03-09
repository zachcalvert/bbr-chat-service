from django.contrib import admin

from .models import GroupMeBot


@admin.register(GroupMeBot)
class GroupMeBotAdmin(admin.ModelAdmin):
    list_display = ['name', 'bot_id', 'group_id', 'is_active', 'voice_display', 'created_at']
    list_filter = ['is_active']
    list_editable = ['is_active']

    def voice_display(self, obj):
        if obj.voice_blend:
            return "Group Blend"
        elif obj.voice:
            return obj.voice.label
        return "—"
    voice_display.short_description = 'Voice'
