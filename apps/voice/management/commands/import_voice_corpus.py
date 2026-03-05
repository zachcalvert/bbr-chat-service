"""Management command to import group chat messages for voice profiles."""
import json
import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.llm_client import llm_client
from apps.voice.models import VoiceMember, VoiceMessage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import group chat messages from a JSON file for voice profiles'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to JSON file with messages')
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of messages to embed per API call (default: 100)',
        )
        parser.add_argument(
            '--min-length',
            type=int,
            default=10,
            help='Minimum message length in characters to include (default: 10)',
        )
        parser.add_argument(
            '--author-field',
            type=str,
            default='author',
            help='JSON field name for the message author (default: author)',
        )
        parser.add_argument(
            '--content-field',
            type=str,
            default='content',
            help='JSON field name for the message content (default: content)',
        )
        parser.add_argument(
            '--timestamp-field',
            type=str,
            default='timestamp',
            help='JSON field name for the message timestamp (default: timestamp)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and report stats without importing',
        )

    def handle(self, *args, **options):
        file_path = options['file']
        batch_size = options['batch_size']
        min_length = options['min_length']
        author_field = options['author_field']
        content_field = options['content_field']
        timestamp_field = options['timestamp_field']
        dry_run = options['dry_run']

        self.stdout.write(f'Loading messages from {file_path}...')
        with open(file_path, 'r') as f:
            raw_messages = json.load(f)

        self.stdout.write(f'Loaded {len(raw_messages)} raw messages')

        # Filter and group by author
        author_messages = {}
        skipped = 0

        for msg in raw_messages:
            author = msg.get(author_field, '').strip()
            content = msg.get(content_field, '').strip()
            timestamp_str = msg.get(timestamp_field)

            if not author or not content:
                skipped += 1
                continue
            if len(content) < min_length:
                skipped += 1
                continue

            timestamp = None
            if timestamp_str:
                try:
                    ts = datetime.fromisoformat(timestamp_str)
                    timestamp = timezone.make_aware(ts) if timezone.is_naive(ts) else ts
                except (ValueError, TypeError):
                    pass

            if author not in author_messages:
                author_messages[author] = []
            author_messages[author].append({
                'content': content,
                'timestamp': timestamp,
            })

        # Report stats
        self.stdout.write(f'\nCorpus stats:')
        total_valid = sum(len(v) for v in author_messages.values())
        self.stdout.write(f'  Total valid messages: {total_valid}')
        self.stdout.write(f'  Skipped messages: {skipped}')
        self.stdout.write(f'  Unique authors: {len(author_messages)}')
        for author, msgs in sorted(author_messages.items(), key=lambda x: -len(x[1])):
            self.stdout.write(f'    {author}: {len(msgs)} messages')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run -- no data imported.'))
            return

        # Create VoiceMember records
        self.stdout.write(f'\nCreating voice members...')
        members = {}
        for author_name, msgs in author_messages.items():
            member, created = VoiceMember.objects.get_or_create(name=author_name)
            member.message_count = len(msgs)
            member.save()
            members[author_name] = member
            status = 'created' if created else 'updated'
            self.stdout.write(f'  {author_name}: {status} ({len(msgs)} messages)')

        # Embed and store messages in batches
        self.stdout.write(f'\nEmbedding and storing messages...')
        total_created = 0
        total_errors = 0

        for author_name, msgs in author_messages.items():
            member = members[author_name]
            self.stdout.write(f'  Processing {author_name} ({len(msgs)} messages)...')

            # Clear existing messages for this member (idempotent)
            existing = member.messages.count()
            if existing > 0:
                member.messages.all().delete()
                self.stdout.write(f'    Cleared {existing} existing messages')

            for i in range(0, len(msgs), batch_size):
                batch = msgs[i:i + batch_size]
                batch_texts = [m['content'] for m in batch]

                try:
                    embeddings = llm_client.embed(batch_texts)

                    if len(embeddings) != len(batch_texts):
                        self.stdout.write(self.style.ERROR(
                            f'    Embedding count mismatch at batch {i}'
                        ))
                        total_errors += len(batch_texts)
                        continue

                    voice_messages = []
                    for msg_data, embedding in zip(batch, embeddings):
                        voice_messages.append(VoiceMessage(
                            member=member,
                            content=msg_data['content'],
                            embedding=embedding,
                            original_timestamp=msg_data['timestamp'],
                        ))
                    VoiceMessage.objects.bulk_create(voice_messages)

                    total_created += len(batch)
                    self.stdout.write(
                        f'    Batch {i // batch_size + 1}: '
                        f'embedded {len(batch)} messages '
                        f'({total_created} total)'
                    )

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'    Batch error: {e}'))
                    total_errors += len(batch_texts)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done! Created {total_created} voice messages, {total_errors} errors'
        ))
