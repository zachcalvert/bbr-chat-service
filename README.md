  To Get Started

  1. Start services:
  docker compose up -d
  2. Pull Ollama models:
  docker compose exec ollama ollama pull llama3.2
  docker compose exec ollama ollama pull nomic-embed-text
  3. Access the app: http://localhost:8000

  Key Features

  - Knowledge Base: Add entries via UI, auto-chunked and embedded
  - Web Crawler: Define topics with keywords, DuckDuckGo discovery, trafilatura extraction
  - Chat Q&A: RAG over both knowledge and crawled content with streaming responses
  - Celery Beat: Automatic scheduled crawling based on topic frequency
