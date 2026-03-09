import logging

import requests

logger = logging.getLogger(__name__)

GROUPME_BOT_POST_URL = 'https://api.groupme.com/v3/bots/post'
GROUPME_MAX_MESSAGE_LENGTH = 1000


def post_message(bot_id: str, text: str) -> bool:
    """Post a message to GroupMe via the bot API.

    Splits long messages into multiple posts to respect the 1000-char limit.
    Returns True if all messages were sent successfully.
    """
    chunks = _split_message(text)
    success = True

    for chunk in chunks:
        try:
            resp = requests.post(
                GROUPME_BOT_POST_URL,
                json={'bot_id': bot_id, 'text': chunk},
                timeout=10,
            )
            if resp.status_code not in (200, 201, 202):
                logger.error(
                    "GroupMe post failed (status %s): %s", resp.status_code, resp.text
                )
                success = False
        except requests.RequestException as e:
            logger.error("GroupMe post request failed: %s", e)
            success = False

    return success


def _split_message(text: str) -> list[str]:
    """Split text into chunks that fit within GroupMe's message limit."""
    if len(text) <= GROUPME_MAX_MESSAGE_LENGTH:
        return [text]

    chunks = []
    while text:
        if len(text) <= GROUPME_MAX_MESSAGE_LENGTH:
            chunks.append(text)
            break

        # Try to split at a newline or space near the limit
        split_at = GROUPME_MAX_MESSAGE_LENGTH
        for sep in ('\n', '. ', ' '):
            idx = text.rfind(sep, 0, GROUPME_MAX_MESSAGE_LENGTH)
            if idx > 0:
                split_at = idx + len(sep)
                break

        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()

    return chunks
