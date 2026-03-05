# BBR Chat Service — Project Summary

A Django-based Retrieval-Augmented Generation (RAG) application for a business incubator. Users can build a knowledge base, crawl the web for topic-specific content, and chat with an AI that draws on all of it.

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Knowledge   │     │   Crawler    │     │      Chat       │
│  (manual)    │     │  (automated) │     │   (RAG query)   │
└──────┬───────┘     └──────┬───────┘     └────────┬────────┘
       │                    │                      │
       │  chunk + embed     │  chunk + embed       │  embed query
       ▼                    ▼                      ▼
┌──────────────────────────────────────────────────────────────┐
│              PostgreSQL + pgvector (768-dim)                  │
│         KnowledgeChunk  &  CrawledChunk vectors              │
└──────────────────────────────────────────────────────────────┘
                            │
                            │  L2 similarity search
                            ▼
                    ┌───────────────┐
                    │  Groq LLM     │
                    │  (llama-3.3)  │
                    └───────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.0 |
| Database | PostgreSQL 16 + pgvector |
| Task Queue | Celery + Redis |
| Embeddings | OpenAI `text-embedding-3-small` (768 dims) |
| Chat LLM | Groq `llama-3.3-70b-versatile` |
| Web Scraping | Trafilatura, DuckDuckGo Search |
| Frontend | Django templates + HTMX (SSE streaming) |
| Deployment | Fly.io (web + worker processes) |
| CI/CD | GitHub Actions → Fly.io |

---

## Django Apps

### `apps/core/` — Shared Utilities & Dashboard

- **LLMClient** (`llm_client.py`) — Unified client for chat (Groq) and embeddings (OpenAI). Methods: `chat()`, `embed()`, `embed_single()`.
- **Text Processing** (`text_processing.py`) — `chunk_text()` splits content into overlapping chunks (default 500 chars, 50 overlap) respecting sentence boundaries. `clean_html_content()` strips HTML.
- **Middleware** (`middleware.py`) — `LoginRequiredMiddleware` enforces auth on all routes except `/login/` and `/admin/`.
- **Dashboard** (`views.py`) — Displays aggregate stats and recent activity.

### `apps/knowledge/` — Knowledge Base

Manual knowledge entry with automatic embedding.

**Models:**
- `KnowledgeEntry` — Title, content, category, source URL.
- `KnowledgeChunk` — Embedded text chunk with 768-dim vector (pgvector).

**How it works:**
1. User creates/edits an entry via the UI.
2. A Django post-save signal (`signals.py`) fires.
3. Content is chunked → embedded via OpenAI → stored as `KnowledgeChunk` rows with vectors.

**Management command:** `reembed_knowledge` — Re-embeds all or specific entries.

### `apps/crawler/` — Web Crawler

Topic-based web crawling with scheduling.

**Models:**
- `Topic` — Keywords, seed URLs, crawl frequency, active flag.
- `CrawlJob` — Execution record (pending → running → completed/failed).
- `CrawledPage` — Fetched page content with URL (unique constraint prevents duplicates).
- `CrawledChunk` — Embedded text chunk with 768-dim vector.

**How it works:**
1. User defines a Topic with keywords and/or seed URLs.
2. Crawl triggered manually or by Celery Beat schedule.
3. URL discovery runs two strategies:
   - **Keyword search** — DuckDuckGo search for each keyword.
   - **Seed URL extraction** — Fetch seed pages, extract same-domain links.
4. Each discovered URL is fetched → Trafilatura extracts main content + metadata.
5. Content is chunked → embedded → stored as `CrawledChunk` rows.

**Celery tasks:**
- `crawl_topic(topic_id, job_id)` — Main crawl orchestrator (3 retries).
- `crawl_due_topics()` — Scheduled task that triggers active topics by frequency.

### `apps/chat/` — RAG Chat Interface

Conversational AI with retrieval-augmented generation.

**Models:**
- `Conversation` — Chat session with auto-generated title.
- `Message` — User or assistant message with source references (JSON).

**RAG Pipeline** (`rag.py`):
1. **Retrieve** — Embed the user's question, run L2 similarity search across both `KnowledgeChunk` and `CrawledChunk` tables, return top-k results (default 5).
2. **Build Context** — Format retrieved chunks with source attribution.
3. **Generate** — Send system prompt + conversation history (last 3 exchanges) + context + question to Groq LLM.
4. **Respond** — Stream response via SSE (HTMX) or return synchronously. Save message with source references.

---

## URL Routes

### Knowledge (`/knowledge/`)
| Method | Path | View |
|---|---|---|
| GET | `/` | `knowledge_list` |
| GET/POST | `/create/` | `knowledge_create` |
| GET | `/<id>/` | `knowledge_detail` |
| GET/POST | `/<id>/edit/` | `knowledge_edit` |
| POST | `/<id>/delete/` | `knowledge_delete` |

### Crawler (`/crawler/`)
| Method | Path | View |
|---|---|---|
| GET | `/` | `topic_list` |
| GET/POST | `/topics/create/` | `topic_create` |
| GET | `/topics/<id>/` | `topic_detail` |
| GET/POST | `/topics/<id>/edit/` | `topic_edit` |
| POST | `/topics/<id>/delete/` | `topic_delete` |
| POST | `/topics/<id>/crawl/` | `topic_crawl` |
| GET | `/pages/` | `page_list` (filterable by topic) |
| GET | `/pages/<id>/` | `page_detail` |
| POST | `/pages/<id>/delete/` | `page_delete` |
| GET | `/jobs/<id>/` | `job_detail` |

### Chat (`/chat/`)
| Method | Path | View |
|---|---|---|
| GET | `/` | `conversation_list` |
| POST | `/new/` | `conversation_new` |
| GET | `/<id>/` | `conversation_view` |
| POST | `/<id>/delete/` | `conversation_delete` |
| POST | `/<id>/send/` | `send_message` (SSE streaming) |

---

## Data Flow

```
               INGESTION                              QUERY
         ┌──────────────────┐                 ┌──────────────────┐
         │                  │                 │                  │
  Manual │  KnowledgeEntry  │          User   │  "What is ...?"  │
  entry  │  ───────────────►│        message  │  ───────────────►│
         │  post-save signal│                 │  embed question  │
         │       │          │                 │       │          │
         │       ▼          │                 │       ▼          │
         │  chunk + embed   │                 │  vector search   │
         │       │          │                 │  (L2 distance)   │
         │       ▼          │                 │       │          │
         │  KnowledgeChunk  │◄────────────────│       │          │
         │  (pgvector)      │  top-k chunks   │       │          │
         └──────────────────┘                 │       ▼          │
                                              │  build context   │
         ┌──────────────────┐                 │       │          │
         │                  │                 │       ▼          │
  Crawl  │  Topic + CrawlJob│                 │  Groq LLM call   │
  task   │  ───────────────►│                 │  (+ history)     │
         │  discover URLs   │                 │       │          │
         │  fetch + extract │                 │       ▼          │
         │  chunk + embed   │                 │  streamed reply  │
         │       │          │                 │  + sources       │
         │       ▼          │                 │                  │
         │  CrawledChunk    │◄────────────────│                  │
         │  (pgvector)      │  top-k chunks   └──────────────────┘
         └──────────────────┘
```

---

## Infrastructure

### Local Development (`docker-compose.yml`)

| Service | Role |
|---|---|
| `db` | PostgreSQL 16 + pgvector |
| `redis` | Celery broker + result backend |
| `web` | Django dev server (port 8000) |
| `celery` | Async task worker |
| `celery-beat` | Periodic task scheduler |

### Production (Fly.io — `fly.toml`)

- **Region:** `ord` (Chicago)
- **Resources:** Shared CPU, 1 vCPU, 512MB RAM
- **Processes:**
  - `web` — Gunicorn with 2 workers
  - `worker` — Celery worker
- **Release command:** Runs migrations + collectstatic on deploy
- **HTTPS:** Forced, auto-start/stop machines enabled

### CI/CD (`.github/workflows/fly-deploy.yml`)

Push to `main` → GitHub Actions → `flyctl deploy`

---

## Configuration

### Key Environment Variables

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Chat completions via Groq |
| `OPENAI_API_KEY` | Embeddings via OpenAI |
| `DATABASE_URL` | PostgreSQL connection string |
| `CELERY_BROKER_URL` | Redis URL for task queue |
| `SECRET_KEY` | Django secret key |
| `DEBUG` | Debug mode toggle |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |

### RAG Settings (`config/settings.py`)

| Setting | Default | Purpose |
|---|---|---|
| `CHAT_MODEL` | `llama-3.3-70b-versatile` | Groq model for chat |
| `EMBED_MODEL` | `text-embedding-3-small` | OpenAI model for embeddings |
| `EMBED_DIMENSIONS` | `768` | Vector dimensionality |
| `RAG_CHUNK_SIZE` | `500` | Characters per chunk |
| `RAG_CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `RAG_TOP_K` | `5` | Chunks retrieved per query |

---

## File Map

```
config/
  settings.py          # Django settings, RAG params, LLM config
  urls.py              # Root URL routing
  celery.py            # Celery app configuration
  wsgi.py              # WSGI entry point

apps/core/
  llm_client.py        # Groq (chat) + OpenAI (embed) client
  text_processing.py   # chunk_text(), clean_html_content()
  middleware.py         # LoginRequiredMiddleware
  views.py             # Dashboard

apps/knowledge/
  models.py            # KnowledgeEntry, KnowledgeChunk
  signals.py           # Post-save auto-chunking + embedding
  views.py             # CRUD views
  forms.py             # KnowledgeEntryForm
  management/commands/reembed_knowledge.py

apps/crawler/
  models.py            # Topic, CrawlJob, CrawledPage, CrawledChunk
  tasks.py             # crawl_topic(), crawl_due_topics()
  views.py             # Topic/page/job management + manual crawl
  forms.py             # TopicForm

apps/chat/
  models.py            # Conversation, Message
  rag.py               # RAGPipeline (retrieve → context → generate)
  views.py             # Chat UI, send_message with SSE streaming

templates/             # Django HTML templates
static/                # CSS assets
docker-compose.yml     # Local dev environment
Dockerfile             # Production container image
fly.toml               # Fly.io deployment config
requirements.txt       # Python dependencies
```
