import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import TopicForm
from .models import CrawledPage, CrawlJob, Topic
from .tasks import crawl_topic

logger = logging.getLogger(__name__)


def topic_list(request):
    """List all topics."""
    topics = Topic.objects.all()
    context = {
        'topics': topics,
    }
    return render(request, 'crawler/topic_list.html', context)


def topic_detail(request, pk):
    """View a topic and its crawled pages."""
    topic = get_object_or_404(Topic, pk=pk)
    pages = topic.crawled_pages.all()[:50]
    jobs = topic.crawl_jobs.all()[:10]
    context = {
        'topic': topic,
        'pages': pages,
        'jobs': jobs,
    }
    return render(request, 'crawler/topic_detail.html', context)


def topic_create(request):
    """Create a new topic."""
    if request.method == 'POST':
        form = TopicForm(request.POST)
        if form.is_valid():
            topic = form.save()
            messages.success(request, f'Topic "{topic.name}" created.')
            return redirect('crawler:topic_detail', pk=topic.pk)
    else:
        form = TopicForm()

    return render(request, 'crawler/topic_form.html', {'form': form, 'action': 'Create'})


def topic_edit(request, pk):
    """Edit a topic."""
    topic = get_object_or_404(Topic, pk=pk)

    if request.method == 'POST':
        form = TopicForm(request.POST, instance=topic)
        if form.is_valid():
            topic = form.save()
            messages.success(request, f'Topic "{topic.name}" updated.')
            return redirect('crawler:topic_detail', pk=topic.pk)
    else:
        form = TopicForm(instance=topic)

    return render(request, 'crawler/topic_form.html', {'form': form, 'action': 'Edit', 'topic': topic})


@require_http_methods(["POST"])
def topic_delete(request, pk):
    """Delete a topic."""
    topic = get_object_or_404(Topic, pk=pk)
    name = topic.name
    topic.delete()
    messages.success(request, f'Topic "{name}" deleted.')
    return redirect('crawler:topic_list')


@require_http_methods(["POST"])
def topic_crawl(request, pk):
    """Trigger a manual crawl for a topic."""
    topic = get_object_or_404(Topic, pk=pk)

    # Create a job and trigger the task
    job = CrawlJob.objects.create(topic=topic)
    crawl_topic.delay(topic.id, job.id)

    messages.info(request, f'Crawl started for "{topic.name}". Check back soon for results.')
    return redirect('crawler:topic_detail', pk=topic.pk)


def page_list(request):
    """List all crawled pages."""
    pages = CrawledPage.objects.select_related('topic').all()

    topic_filter = request.GET.get('topic')
    if topic_filter:
        pages = pages.filter(topic_id=topic_filter)

    context = {
        'pages': pages[:100],
        'topics': Topic.objects.all(),
        'current_topic': topic_filter,
    }
    return render(request, 'crawler/page_list.html', context)


def page_detail(request, pk):
    """View a crawled page."""
    page = get_object_or_404(CrawledPage, pk=pk)
    chunks = page.chunks.all()
    context = {
        'page': page,
        'chunks': chunks,
    }
    return render(request, 'crawler/page_detail.html', context)


@require_http_methods(["POST"])
def page_delete(request, pk):
    """Delete a crawled page."""
    page = get_object_or_404(CrawledPage, pk=pk)
    topic_pk = page.topic.pk
    page.delete()
    messages.success(request, 'Page deleted.')
    return redirect('crawler:topic_detail', pk=topic_pk)


def job_detail(request, pk):
    """View a crawl job."""
    job = get_object_or_404(CrawlJob, pk=pk)
    pages = job.pages.all()
    context = {
        'job': job,
        'pages': pages,
    }
    return render(request, 'crawler/job_detail.html', context)
