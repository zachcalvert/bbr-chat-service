"""Text processing utilities for chunking content."""
import re
from typing import Iterator

from django.conf import settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> Iterator[tuple[int, str]]:
    """
    Split text into overlapping chunks.

    Args:
        text: The text to chunk
        chunk_size: Maximum characters per chunk
        overlap: Number of overlapping characters between chunks

    Yields:
        Tuples of (chunk_index, chunk_content)
    """
    chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
    overlap = overlap or settings.RAG_CHUNK_OVERLAP

    # Clean and normalize text
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) <= chunk_size:
        yield (0, text)
        return

    # Split into sentences first for better boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)

    current_chunk = ""
    chunk_index = 0

    for sentence in sentences:
        # If adding this sentence exceeds chunk size
        if len(current_chunk) + len(sentence) + 1 > chunk_size:
            if current_chunk:
                yield (chunk_index, current_chunk.strip())
                chunk_index += 1

                # Create overlap from end of current chunk
                overlap_text = current_chunk[-overlap:] if overlap > 0 else ""
                current_chunk = overlap_text + " " + sentence
            else:
                # Sentence itself is too long, split by words
                words = sentence.split()
                for word in words:
                    if len(current_chunk) + len(word) + 1 > chunk_size:
                        if current_chunk:
                            yield (chunk_index, current_chunk.strip())
                            chunk_index += 1
                            overlap_text = current_chunk[-overlap:] if overlap > 0 else ""
                            current_chunk = overlap_text + " " + word
                        else:
                            # Word itself exceeds chunk size, truncate
                            yield (chunk_index, word[:chunk_size])
                            chunk_index += 1
                            current_chunk = ""
                    else:
                        current_chunk = current_chunk + " " + word if current_chunk else word
        else:
            current_chunk = current_chunk + " " + sentence if current_chunk else sentence

    # Yield remaining text
    if current_chunk.strip():
        yield (chunk_index, current_chunk.strip())


def clean_html_content(html: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    # Remove script and style elements
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)

    # Decode HTML entities
    import html as html_module
    text = html_module.unescape(text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text
