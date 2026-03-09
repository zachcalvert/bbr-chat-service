from django.contrib import admin

from .models import CallbackLog, GroupMeBot


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


@admin.register(CallbackLog)
class CallbackLogAdmin(admin.ModelAdmin):
    list_display = [
        'received_at', 'sender_name', 'outcome', 'bot',
        'message_preview', 'duration_ms',
    ]
    list_filter = ['outcome', 'bot', 'received_at']
    search_fields = ['sender_name', 'sender_id', 'message_text', 'response_text']
    readonly_fields = [
        'received_at', 'payload', 'sender_type', 'sender_name', 'sender_id',
        'message_text', 'bot', 'outcome', 'response_text', 'error_message',
        'duration_ms',
    ]
    date_hierarchy = 'received_at'

    def message_preview(self, obj):
        if not obj.message_text:
            return "—"
        return obj.message_text[:80] + ("…" if len(obj.message_text) > 80 else "")
    message_preview.short_description = 'Message'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
