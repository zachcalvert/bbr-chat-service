from django.contrib import admin

from .models import VoiceMember, VoiceMessage


class VoiceMessageInline(admin.TabularInline):
    model = VoiceMessage
    extra = 0
    readonly_fields = ['content', 'original_timestamp', 'created_at']
    can_delete = False
    max_num = 20

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(VoiceMember)
class VoiceMemberAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'message_count', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']
    readonly_fields = ['name', 'message_count', 'created_at', 'updated_at']
    fields = ['display_name', 'name', 'is_active', 'message_count', 'created_at', 'updated_at']
    inlines = [VoiceMessageInline]


@admin.register(VoiceMessage)
class VoiceMessageAdmin(admin.ModelAdmin):
    list_display = ['member', 'content_preview', 'original_timestamp', 'created_at']
    list_filter = ['member']
    search_fields = ['content']
    readonly_fields = ['embedding']

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
