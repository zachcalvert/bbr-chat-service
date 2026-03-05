from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import KnowledgeEntryForm
from .models import KnowledgeEntry


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
            # Chunks are created automatically via post_save signal
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
            # Delete existing chunks so signal will re-create them
            entry.chunks.all().delete()
            entry = form.save()
            # Chunks are re-created automatically via post_save signal
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
