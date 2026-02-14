import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.ollama_client import ollama_client
from apps.core.text_processing import chunk_text

from .forms import KnowledgeEntryForm
from .models import KnowledgeChunk, KnowledgeEntry

logger = logging.getLogger(__name__)


def knowledge_list(request):
    """List all knowledge entries."""
    entries = KnowledgeEntry.objects.all()
    categories = KnowledgeEntry.objects.values_list('category', flat=True).distinct()
    categories = [c for c in categories if c]

    category_filter = request.GET.get('category')
    if category_filter:
        entries = entries.filter(category=category_filter)

    context = {
        'entries': entries,
        'categories': categories,
        'current_category': category_filter,
    }
    return render(request, 'knowledge/list.html', context)


def knowledge_detail(request, pk):
    """View a knowledge entry."""
    entry = get_object_or_404(KnowledgeEntry, pk=pk)
    chunks = entry.chunks.all()
    context = {
        'entry': entry,
        'chunks': chunks,
    }
    return render(request, 'knowledge/detail.html', context)


def knowledge_create(request):
    """Create a new knowledge entry."""
    if request.method == 'POST':
        form = KnowledgeEntryForm(request.POST)
        if form.is_valid():
            entry = form.save()
            _process_entry_chunks(entry)
            messages.success(request, f'Knowledge entry "{entry.title}" created and embedded.')
            return redirect('knowledge:detail', pk=entry.pk)
    else:
        form = KnowledgeEntryForm()

    return render(request, 'knowledge/form.html', {'form': form, 'action': 'Create'})


def knowledge_edit(request, pk):
    """Edit a knowledge entry."""
    entry = get_object_or_404(KnowledgeEntry, pk=pk)

    if request.method == 'POST':
        form = KnowledgeEntryForm(request.POST, instance=entry)
        if form.is_valid():
            entry = form.save()
            # Re-chunk and re-embed on update
            entry.chunks.all().delete()
            _process_entry_chunks(entry)
            messages.success(request, f'Knowledge entry "{entry.title}" updated.')
            return redirect('knowledge:detail', pk=entry.pk)
    else:
        form = KnowledgeEntryForm(instance=entry)

    return render(request, 'knowledge/form.html', {'form': form, 'action': 'Edit', 'entry': entry})


@require_http_methods(["POST"])
def knowledge_delete(request, pk):
    """Delete a knowledge entry."""
    entry = get_object_or_404(KnowledgeEntry, pk=pk)
    title = entry.title
    entry.delete()
    messages.success(request, f'Knowledge entry "{title}" deleted.')
    return redirect('knowledge:list')


def _process_entry_chunks(entry: KnowledgeEntry) -> None:
    """Chunk and embed a knowledge entry."""
    try:
        chunks_to_create = []
        chunk_texts = []

        for chunk_index, chunk_content in chunk_text(entry.content):
            chunk_texts.append(chunk_content)
            chunks_to_create.append({
                'entry': entry,
                'content': chunk_content,
                'chunk_index': chunk_index,
            })

        if chunk_texts:
            # Get embeddings for all chunks
            embeddings = ollama_client.embed(chunk_texts)

            # Create chunk objects with embeddings
            for chunk_data, embedding in zip(chunks_to_create, embeddings):
                KnowledgeChunk.objects.create(
                    entry=chunk_data['entry'],
                    content=chunk_data['content'],
                    chunk_index=chunk_data['chunk_index'],
                    embedding=embedding,
                )

            logger.info(f"Created {len(chunks_to_create)} chunks for entry {entry.pk}")

    except Exception as e:
        logger.error(f"Error processing chunks for entry {entry.pk}: {e}")
        raise
