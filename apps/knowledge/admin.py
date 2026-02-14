from django.contrib import admin

from .models import KnowledgeChunk, KnowledgeEntry


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    extra = 0
    readonly_fields = ['chunk_index', 'content']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'created_at', 'updated_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'content']
    inlines = [KnowledgeChunkInline]


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ['entry', 'chunk_index', 'content_preview']
    list_filter = ['entry']
    readonly_fields = ['embedding']

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
