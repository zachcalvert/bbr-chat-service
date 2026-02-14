from django.shortcuts import render

from apps.knowledge.models import KnowledgeEntry, KnowledgeChunk
from apps.crawler.models import Topic, CrawledPage, CrawledChunk
from apps.chat.models import Conversation


def dashboard(request):
    context = {
        'knowledge_count': KnowledgeEntry.objects.count(),
        'knowledge_chunks': KnowledgeChunk.objects.count(),
        'topics_count': Topic.objects.filter(is_active=True).count(),
        'crawled_pages': CrawledPage.objects.count(),
        'crawled_chunks': CrawledChunk.objects.count(),
        'conversations': Conversation.objects.count(),
        'recent_pages': CrawledPage.objects.order_by('-crawled_at')[:5],
        'recent_knowledge': KnowledgeEntry.objects.order_by('-updated_at')[:5],
    }
    return render(request, 'core/dashboard.html', context)
