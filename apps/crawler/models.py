from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimestampedModel


class Topic(TimestampedModel):
    """A topic to crawl with associated keywords."""

    name = models.CharField(max_length=255)
    keywords = models.JSONField(
        default=list,
        help_text="List of keywords to search for"
    )
    is_active = models.BooleanField(default=True)
    crawl_frequency_hours = models.IntegerField(
        default=24,
        help_text="How often to crawl this topic (in hours)"
    )
    max_pages_per_crawl = models.IntegerField(
        default=10,
        help_text="Maximum pages to crawl per run"
    )
    last_crawled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def keywords_display(self):
        return ", ".join(self.keywords) if self.keywords else "None"


class CrawlJob(TimestampedModel):
    """A single crawl job execution."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='crawl_jobs'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    pages_discovered = models.IntegerField(default=0)
    pages_crawled = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.topic.name} - {self.created_at}"


class CrawledPage(TimestampedModel):
    """A web page that has been crawled."""

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='crawled_pages'
    )
    crawl_job = models.ForeignKey(
        CrawlJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pages'
    )
    url = models.URLField(max_length=2000, unique=True)
    title = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    crawled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-crawled_at']

    def __str__(self):
        return self.title or self.url


class CrawledChunk(models.Model):
    """An embedded chunk of a crawled page for vector search."""

    page = models.ForeignKey(
        CrawledPage,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    content = models.TextField()
    embedding = VectorField(dimensions=768)
    chunk_index = models.IntegerField()

    class Meta:
        ordering = ['page', 'chunk_index']
        unique_together = ['page', 'chunk_index']

    def __str__(self):
        return f"{self.page.title or self.page.url} - Chunk {self.chunk_index}"
