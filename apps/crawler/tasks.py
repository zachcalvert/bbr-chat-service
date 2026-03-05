import logging
from datetime import timedelta
from urllib.parse import urlparse

import requests
import trafilatura
from celery import shared_task
from django.utils import timezone
from duckduckgo_search import DDGS

from apps.core.llm_client import llm_client
from apps.core.text_processing import chunk_text

from .models import CrawledChunk, CrawledPage, CrawlJob, Topic

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def crawl_topic(self, topic_id: int, job_id: int | None = None):
    """
    Crawl a topic: discover URLs, fetch content, chunk and embed.

    Args:
        topic_id: The Topic ID to crawl
        job_id: Optional CrawlJob ID if already created
    """
    try:
        topic = Topic.objects.get(pk=topic_id)
    except Topic.DoesNotExist:
        logger.error(f"Topic {topic_id} not found")
        return

    # Create or get crawl job
    if job_id:
        try:
            job = CrawlJob.objects.get(pk=job_id)
        except CrawlJob.DoesNotExist:
            job = CrawlJob.objects.create(topic=topic)
    else:
        job = CrawlJob.objects.create(topic=topic)

    job.status = CrawlJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save()

    try:
        # Discover URLs from seed pages and keyword search
        all_urls = []

        if topic.seed_urls:
            seed_discovered = discover_urls_from_seeds(
                topic.seed_urls,
                max_results=topic.max_pages_per_crawl,
            )
            all_urls.extend(seed_discovered)
            logger.info(f"Discovered {len(seed_discovered)} URLs from seed URLs for topic {topic.name}")

        if topic.keywords:
            remaining_slots = topic.max_pages_per_crawl - len(all_urls)
            if remaining_slots > 0:
                keyword_discovered = discover_urls(topic.keywords, max_results=remaining_slots)
                for url in keyword_discovered:
                    if url not in all_urls:
                        all_urls.append(url)
                logger.info(f"Discovered {len(keyword_discovered)} URLs from keywords for topic {topic.name}")

        urls = all_urls[:topic.max_pages_per_crawl]
        job.pages_discovered = len(urls)
        job.save()

        logger.info(f"Discovered {len(urls)} total URLs for topic {topic.name}")

        # Crawl each URL
        crawled_count = 0
        for url in urls:
            # Skip if already crawled
            if CrawledPage.objects.filter(url=url).exists():
                logger.debug(f"Skipping already crawled URL: {url}")
                continue

            try:
                page = crawl_url(url, topic, job)
                if page:
                    process_page_chunks(page)
                    crawled_count += 1
            except Exception as e:
                logger.warning(f"Error crawling {url}: {e}")
                continue

        job.pages_crawled = crawled_count
        job.status = CrawlJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.save()

        # Update topic last crawled time
        topic.last_crawled_at = timezone.now()
        topic.save()

        logger.info(f"Completed crawl for topic {topic.name}: {crawled_count} pages")

    except Exception as e:
        logger.error(f"Crawl job failed for topic {topic.name}: {e}")
        job.status = CrawlJob.Status.FAILED
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        raise self.retry(exc=e, countdown=60)


def discover_urls(keywords: list[str], max_results: int = 10) -> list[str]:
    """
    Discover URLs using DuckDuckGo search.

    Args:
        keywords: List of keywords to search
        max_results: Maximum URLs to return

    Returns:
        List of discovered URLs
    """
    if not keywords:
        return []

    urls = []

    try:
        with DDGS() as ddgs:
            for keyword in keywords:
                results = ddgs.text(keyword, max_results=max_results // len(keywords) + 1)
                for result in results:
                    url = result.get('href', '')
                    if url and url not in urls:
                        urls.append(url)

                    if len(urls) >= max_results:
                        break

                if len(urls) >= max_results:
                    break

    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")

    return urls[:max_results]


def discover_urls_from_seeds(seed_urls: list[str], max_results: int = 10) -> list[str]:
    """
    Discover URLs by fetching seed pages and extracting same-domain links.

    Args:
        seed_urls: List of seed URLs to fetch and extract links from
        max_results: Maximum URLs to return

    Returns:
        List of discovered URLs (including the seed URLs themselves)
    """
    from lxml import html as lxml_html

    discovered = []

    for seed_url in seed_urls:
        if seed_url not in discovered:
            discovered.append(seed_url)

        try:
            response = requests.get(
                seed_url,
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; IncubatorBot/1.0; +http://localhost)'
                },
            )
            response.raise_for_status()

            tree = lxml_html.fromstring(response.text)
            tree.make_links_absolute(seed_url)

            seed_domain = urlparse(seed_url).netloc

            for element, attribute, link, pos in tree.iterlinks():
                if attribute != 'href':
                    continue

                parsed = urlparse(link)
                if parsed.netloc != seed_domain:
                    continue
                if parsed.scheme not in ('http', 'https'):
                    continue

                clean_url = parsed._replace(fragment='').geturl()

                if clean_url not in discovered:
                    discovered.append(clean_url)

                if len(discovered) >= max_results:
                    break

        except Exception as e:
            logger.warning(f"Error extracting links from seed URL {seed_url}: {e}")
            continue

        if len(discovered) >= max_results:
            break

    return discovered[:max_results]


def crawl_url(url: str, topic: Topic, job: CrawlJob) -> CrawledPage | None:
    """
    Fetch and extract content from a URL.

    Args:
        url: The URL to crawl
        topic: The Topic this URL belongs to
        job: The CrawlJob this is part of

    Returns:
        CrawledPage if successful, None otherwise
    """
    try:
        # Fetch the page
        response = requests.get(
            url,
            timeout=30,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; IncubatorBot/1.0; +http://localhost)'
            }
        )
        response.raise_for_status()

        # Extract content using trafilatura
        content = trafilatura.extract(
            response.text,
            include_links=False,
            include_images=False,
            include_tables=True,
        )

        if not content or len(content) < 100:
            logger.debug(f"Insufficient content from {url}")
            return None

        # Extract title
        title = trafilatura.extract_metadata(response.text)
        title_str = ""
        if title and title.title:
            title_str = title.title[:500]

        # Create page record
        page = CrawledPage.objects.create(
            topic=topic,
            crawl_job=job,
            url=url,
            title=title_str,
            content=content,
        )

        logger.info(f"Crawled: {title_str or url}")
        return page

    except requests.RequestException as e:
        logger.warning(f"Request error for {url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error extracting content from {url}: {e}")
        return None


def process_page_chunks(page: CrawledPage) -> None:
    """
    Chunk and embed a crawled page.

    Args:
        page: The CrawledPage to process
    """
    try:
        chunks_to_create = []
        chunk_texts = []

        for chunk_index, chunk_content in chunk_text(page.content):
            chunk_texts.append(chunk_content)
            chunks_to_create.append({
                'page': page,
                'content': chunk_content,
                'chunk_index': chunk_index,
            })

        if chunk_texts:
            # Get embeddings for all chunks
            embeddings = llm_client.embed(chunk_texts)

            # Create chunk objects with embeddings
            for chunk_data, embedding in zip(chunks_to_create, embeddings):
                CrawledChunk.objects.create(
                    page=chunk_data['page'],
                    content=chunk_data['content'],
                    chunk_index=chunk_data['chunk_index'],
                    embedding=embedding,
                )

            logger.debug(f"Created {len(chunks_to_create)} chunks for page {page.pk}")

    except Exception as e:
        logger.error(f"Error processing chunks for page {page.pk}: {e}")
        raise


@shared_task
def crawl_due_topics():
    """
    Celery Beat task to crawl topics that are due.
    Checks all active topics and triggers crawls for those past their frequency.
    """
    now = timezone.now()

    topics = Topic.objects.filter(is_active=True)

    for topic in topics:
        # Check if topic is due for crawling
        if topic.last_crawled_at is None:
            should_crawl = True
        else:
            next_crawl = topic.last_crawled_at + timedelta(hours=topic.crawl_frequency_hours)
            should_crawl = now >= next_crawl

        if should_crawl:
            logger.info(f"Triggering crawl for topic: {topic.name}")
            crawl_topic.delay(topic.id)
