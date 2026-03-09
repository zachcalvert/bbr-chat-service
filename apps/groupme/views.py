import json
import logging
import re

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.chat.rag import rag_pipeline

from .client import post_message
from .models import GroupMeBot

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def groupme_callback(request):
    """Callback endpoint for GroupMe webhooks.

    Receives the native GroupMe message payload, checks for bot mentions,
    runs RAG with optional voice translation, and posts the response back.
    Always returns 204 as GroupMe expects.
    """
    # Auth check
    auth_header = request.headers.get('Authorization', '')
    expected = settings.API_SECRET_KEY
    if expected and (not auth_header.startswith('Bearer ') or auth_header[7:] != expected):
        return HttpResponse(status=401)

    try:
        content = json.loads(request.body)
    except json.JSONDecodeError:
        logger.error("Failed to parse GroupMe callback payload")
        return HttpResponse(status=204)

    # Ignore bot messages to prevent loops
    if content.get("sender_type") == "bot":
        return HttpResponse(status=204)

    message_text = content.get("text", "")
    if not message_text:
        return HttpResponse(status=204)

    sender_name = content.get("name", "Unknown")
    user_id = content.get("user_id", "")

    for bot in GroupMeBot.objects.filter(is_active=True):
        # Case-insensitive mention check
        if bot.name.lower() not in message_text.lower():
            continue

        logger.info("GroupMe message for %s from %s: %s", bot.name, sender_name, message_text)

        # Strip the bot name from the text to get the actual question
        question = re.sub(re.escape(bot.name), '', message_text, flags=re.IGNORECASE).strip()

        if not question:
            continue

        try:
            response, _chunks = rag_pipeline.query_with_voice(
                question=question,
                voice_member=bot.voice,
                voice_blend=bot.voice_blend,
                stream=False,
            )
        except Exception as e:
            logger.error("RAG error for bot %s: %s", bot.name, e)
            continue

        try:
            post_message(bot.bot_id, response)
        except Exception as e:
            logger.error("Failed to post GroupMe response for bot %s: %s", bot.name, e)

    return HttpResponse(status=204)
