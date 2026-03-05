"""Fetch all messages from a GroupMe group and save as JSON for voice import."""
import datetime
import json
import re
import time

import requests
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Fetch GroupMe messages into a JSON file for import_voice_corpus'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            required=True,
            help='GroupMe API token',
        )
        parser.add_argument(
            '--group-id',
            type=str,
            required=True,
            help='GroupMe group ID',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='groupme_messages.json',
            help='Output JSON file path (default: groupme_messages.json)',
        )
        parser.add_argument(
            '--after-id',
            type=str,
            default=None,
            help='Start collecting after this message ID (for resuming)',
        )
        parser.add_argument(
            '--max-batches',
            type=int,
            default=2000,
            help='Maximum number of API batches to fetch (default: 2000, ~200k messages)',
        )

    def strip_urls(self, text):
        if not text:
            return text
        try:
            return re.sub(r'https?://\S+', '', text, flags=re.MULTILINE).strip()
        except TypeError:
            return text

    def handle(self, *args, **options):
        token = options['token']
        group_id = options['group_id']
        output_path = options['output']
        after_id = options['after_id']
        max_batches = options['max_batches']

        base_url = f"https://api.groupme.com/v3/groups/{group_id}/messages"
        all_messages = []

        self.stdout.write(f'Fetching messages from group {group_id}...')

        try:
            for batch_num in range(max_batches):
                url = f"{base_url}?token={token}&limit=100"
                if after_id:
                    url += f"&after_id={after_id}"

                response = requests.get(url)

                if response.status_code != 200:
                    self.stdout.write(self.style.WARNING(
                        f'API returned {response.status_code}, stopping.'
                    ))
                    break

                data = response.json()
                message_list = data.get('response', {}).get('messages', [])

                if not message_list:
                    self.stdout.write('No more messages to collect.')
                    break

                for msg in message_list:
                    text = self.strip_urls(msg.get('text'))
                    if not text:
                        continue

                    created_at = datetime.datetime.fromtimestamp(
                        msg['created_at'],
                        tz=datetime.timezone.utc,
                    )

                    all_messages.append({
                        'creator': str(msg.get('user_id', '')).strip(),
                        'text': text,
                        'create_date': created_at.isoformat(),
                    })

                # Set after_id to the last message in this batch for pagination
                after_id = message_list[-1]['id']

                if batch_num % 10 == 0:
                    self.stdout.write(
                        f'  Batch {batch_num + 1}: {len(all_messages)} messages collected'
                    )

                time.sleep(0.5)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nInterrupted by user.'))

        # Always save what we have
        self.stdout.write(f'\nSaving {len(all_messages)} messages to {output_path}...')
        with open(output_path, 'w') as f:
            json.dump(all_messages, f, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f'Done! Saved {len(all_messages)} messages to {output_path}'
        ))
        self.stdout.write(f'\nTo import, run:')
        self.stdout.write(
            f'  python manage.py import_voice_corpus {output_path} '
            f'--author-field creator --content-field text --timestamp-field create_date'
        )
