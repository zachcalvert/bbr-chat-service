"""Management command to re-embed voice messages."""
import logging

from django.core.management.base import BaseCommand

from apps.core.llm_client import llm_client
from apps.voice.models import VoiceMember, VoiceMessage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Re-embed voice messages for a specific member or all members'

    def add_arguments(self, parser):
        parser.add_argument(
            '--member',
            type=str,
            help='Name of a specific member to re-embed',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of messages to embed per API call (default: 100)',
        )

    def handle(self, *args, **options):
        member_name = options.get('member')
        batch_size = options['batch_size']

        if member_name:
            members = VoiceMember.objects.filter(name=member_name)
        else:
            members = VoiceMember.objects.all()

        if not members.exists():
            self.stdout.write(self.style.WARNING('No members found'))
            return

        for member in members:
            messages = list(VoiceMessage.objects.filter(member=member))
            count = len(messages)
            self.stdout.write(f'Re-embedding {count} messages for {member.name}...')

            updated = 0
            for i in range(0, count, batch_size):
                batch = messages[i:i + batch_size]
                texts = [m.content for m in batch]

                try:
                    embeddings = llm_client.embed(texts)
                    for msg, embedding in zip(batch, embeddings):
                        msg.embedding = embedding
                    VoiceMessage.objects.bulk_update(batch, ['embedding'])
                    updated += len(batch)
                    self.stdout.write(f'  Batch {i // batch_size + 1}: updated {len(batch)}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Batch error: {e}'))

            self.stdout.write(self.style.SUCCESS(f'  Updated {updated}/{count} messages'))
