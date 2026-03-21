# BBR Chat Service

A RAG (Retrieval-Augmented Generation) chat application for the BBR fantasy football league. Ask questions about league history, memorable moments, trades, scores, and more — get accurate, context-grounded answers drawn from a curated knowledge base and crawled web content, optionally delivered in the writing voice of a league member from your group chat.

## Stack

- **Framework:** Django 5.0
- **Database:** PostgreSQL 16 + pgvector (vector similarity search)
- **Task queue:** Celery + Redis
- **Embeddings:** OpenAI `text-embedding-3-small`
- **Chat LLM:** Groq `llama-3.3-70b-versatile`
- **Web scraping:** Trafilatura + DuckDuckGo Search
- **Frontend:** Django templates + HTMX (SSE streaming)
- **Deployment:** Fly.io + Neon Postgres

## Features

- **Knowledge Base** — Manually add entries via UI; content is automatically chunked and embedded on save
- **Web Crawler** — Define topics with keywords and seed URLs; DuckDuckGo discovery + link extraction; Trafilatura content extraction; scheduled via Celery Beat
- **RAG Chat** — Semantic search across knowledge and crawled content; streaming responses via SSE; conversation history; source attribution
- **Voice Translation** — A second LLM pass rewrites RAG responses in the writing style of a specific person, drawn from an embedded corpus of real group chat messages

## Local Development

**Prerequisites:** Docker + Docker Compose

1. Copy the example env file and fill in your API keys:
   ```
   cp .env.example .env
   ```
   Required keys: `GROQ_API_KEY`, `OPENAI_API_KEY`

2. Start all services:
   ```
   docker compose up -d
   ```

3. Open the app: [http://localhost:8000](http://localhost:8000)

   Default login is set up via Django's admin — create a superuser first:
   ```
   docker compose exec web python manage.py createsuperuser
   ```

## Voice Corpus Setup

To enable voice translation, import a group chat corpus:

1. Fetch messages from GroupMe:
   ```
   docker compose exec web python manage.py fetch_groupme \
     --token YOUR_TOKEN \
     --group-id YOUR_GROUP_ID \
     --after-id FIRST_MESSAGE_ID \
     --output /app/messages.json
   ```

2. Preview the corpus (dry run):
   ```
   docker compose exec web python manage.py import_voice_corpus /app/messages.json \
     --author-field creator --content-field text --timestamp-field create_date \
     --dry-run
   ```

3. Import and embed:
   ```
   docker compose exec web python manage.py import_voice_corpus /app/messages.json \
     --author-field creator --content-field text --timestamp-field create_date
   ```

4. Name your members at `/admin/voice/voicemember/` — set `display_name` for each user ID.

See [`docs/VOICE_TRANSLATION.md`](docs/VOICE_TRANSLATION.md) for full details.

## Deployment

The app deploys to Fly.io via GitHub Actions on push to `main`.

```
flyctl deploy
```

Database is hosted on Neon (Postgres + pgvector). Set `DATABASE_URL` in Fly secrets.

## Documentation

- [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md) — full architecture overview, data flow, and file map
- [`docs/VOICE_TRANSLATION.md`](docs/VOICE_TRANSLATION.md) — voice translation pipeline, corpus setup, and configuration
