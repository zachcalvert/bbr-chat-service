import json
import logging
import re
import time

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.chat.rag import rag_pipeline

from .client import post_message
from .models import CallbackLog, GroupMeBot

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

    sender_type = content.get("sender_type", "")
    sender_name = content.get("name", "")
    sender_id = content.get("user_id", "")
    message_text = content.get("text", "")

    # Ignore bot messages to prevent loops
    if sender_type == "bot":
        CallbackLog.objects.create(
            payload=content,
            sender_type=sender_type,
            sender_name=sender_name,
            sender_id=sender_id,
            message_text=message_text,
            outcome=CallbackLog.Outcome.IGNORED,
        )
        return HttpResponse(status=204)

    if not message_text:
        CallbackLog.objects.create(
            payload=content,
            sender_type=sender_type,
            sender_name=sender_name,
            sender_id=sender_id,
            outcome=CallbackLog.Outcome.IGNORED,
        )
        return HttpResponse(status=204)

    for bot in GroupMeBot.objects.filter(is_active=True):
        start = time.monotonic()

        # Case-insensitive mention check
        if bot.name.lower() not in message_text.lower():
            continue

        logger.info("GroupMe message for %s from %s: %s", bot.name, sender_name, message_text)

        # Strip the bot name from the text to get the actual question
        question = re.sub(re.escape(bot.name), '', message_text, flags=re.IGNORECASE).strip()

        if not question:
            CallbackLog.objects.create(
                payload=content,
                sender_type=sender_type,
                sender_name=sender_name,
                sender_id=sender_id,
                message_text=message_text,
                bot=bot,
                outcome=CallbackLog.Outcome.IGNORED,
            )
            continue

        try:
            response_text, _chunks = rag_pipeline.query_with_voice(
                question=question,
                voice_member=bot.voice,
                voice_blend=bot.voice_blend,
                stream=False,
            )
        except Exception as e:
            logger.error("RAG error for bot %s: %s", bot.name, e)
            CallbackLog.objects.create(
                payload=content,
                sender_type=sender_type,
                sender_name=sender_name,
                sender_id=sender_id,
                message_text=message_text,
                bot=bot,
                outcome=CallbackLog.Outcome.ERROR,
                error_message=f"RAG error: {e}",
                duration_ms=_elapsed_ms(start),
            )
            continue

        try:
            post_message(bot.bot_id, response_text)
        except Exception as e:
            logger.error("Failed to post GroupMe response for bot %s: %s", bot.name, e)
            CallbackLog.objects.create(
                payload=content,
                sender_type=sender_type,
                sender_name=sender_name,
                sender_id=sender_id,
                message_text=message_text,
                bot=bot,
                outcome=CallbackLog.Outcome.ERROR,
                response_text=response_text,
                error_message=f"GroupMe post error: {e}",
                duration_ms=_elapsed_ms(start),
            )
            continue

        CallbackLog.objects.create(
            payload=content,
            sender_type=sender_type,
            sender_name=sender_name,
            sender_id=sender_id,
            message_text=message_text,
            bot=bot,
            outcome=CallbackLog.Outcome.RESPONDED,
            response_text=response_text,
            duration_ms=_elapsed_ms(start),
        )

    return HttpResponse(status=204)


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
