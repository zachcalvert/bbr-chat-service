"""Management command to re-embed knowledge entries."""
from django.core.management.base import BaseCommand

from apps.core.ollama_client import ollama_client
from apps.core.text_processing import chunk_text
from apps.knowledge.models import KnowledgeChunk, KnowledgeEntry


class Command(BaseCommand):
    help = 'Re-embed all knowledge entries (or specific ones by ID)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ids',
            nargs='+',
            type=int,
            help='Specific entry IDs to re-embed',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-embed even if chunks already exist',
        )

    def handle(self, *args, **options):
        entry_ids = options.get('ids')
        force = options.get('force', False)

        # Get entries to process
        if entry_ids:
            entries = KnowledgeEntry.objects.filter(pk__in=entry_ids)
        else:
            entries = KnowledgeEntry.objects.all()

        if not entries.exists():
            self.stdout.write(self.style.WARNING('No entries found to process'))
            return

        # Check Ollama connectivity
        if not ollama_client.is_healthy():
            self.stdout.write(self.style.ERROR('Ollama server is not reachable'))
            return

        self.stdout.write(f'Processing {entries.count()} entries...')

        success_count = 0
        error_count = 0

        for entry in entries:
            existing_chunks = entry.chunks.count()

            if existing_chunks > 0 and not force:
                self.stdout.write(
                    f'  Skipping "{entry.title}" - already has {existing_chunks} chunks '
                    f'(use --force to re-embed)'
                )
                continue

            self.stdout.write(f'  Processing "{entry.title}"...')

            try:
                # Delete existing chunks
                entry.chunks.all().delete()

                # Generate new chunks
                chunks_data = []
                chunk_texts = []

                for chunk_index, chunk_content in chunk_text(entry.content):
                    chunk_texts.append(chunk_content)
                    chunks_data.append({
                        'entry': entry,
                        'content': chunk_content,
                        'chunk_index': chunk_index,
                    })

                if not chunk_texts:
                    self.stdout.write(self.style.WARNING(f'    No chunks generated'))
                    continue

                # Get embeddings
                self.stdout.write(f'    Embedding {len(chunk_texts)} chunks...')
                embeddings = ollama_client.embed(chunk_texts)

                if not embeddings or len(embeddings) != len(chunk_texts):
                    self.stdout.write(self.style.ERROR(f'    Embedding failed'))
                    error_count += 1
                    continue

                # Create chunks
                for data, embedding in zip(chunks_data, embeddings):
                    KnowledgeChunk.objects.create(
                        entry=data['entry'],
                        content=data['content'],
                        chunk_index=data['chunk_index'],
                        embedding=embedding,
                    )

                self.stdout.write(self.style.SUCCESS(f'    Created {len(chunks_data)} chunks'))
                success_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    Error: {e}'))
                error_count += 1

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'Done! Processed {success_count} entries, {error_count} errors')
        )
