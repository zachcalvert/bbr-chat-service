from django.contrib import admin

from .models import CrawledChunk, CrawledPage, CrawlJob, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'keywords_display', 'crawl_frequency_hours', 'last_crawled_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(CrawlJob)
class CrawlJobAdmin(admin.ModelAdmin):
    list_display = ['topic', 'status', 'pages_discovered', 'pages_crawled', 'created_at']
    list_filter = ['status', 'topic']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(CrawledPage)
class CrawledPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'topic', 'url', 'crawled_at']
    list_filter = ['topic', 'crawled_at']
    search_fields = ['title', 'url', 'content']


@admin.register(CrawledChunk)
class CrawledChunkAdmin(admin.ModelAdmin):
    list_display = ['page', 'chunk_index', 'content_preview']
    list_filter = ['page__topic']

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
