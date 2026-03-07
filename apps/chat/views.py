import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.voice.models import VoiceMember

from .models import Conversation, Message
from .rag import rag_pipeline

logger = logging.getLogger(__name__)


def conversation_list(request):
    """List all conversations."""
    conversations = Conversation.objects.all()
    context = {
        'conversations': conversations,
    }
    return render(request, 'chat/list.html', context)


def conversation_new(request):
    """Start a new conversation."""
    conversation = Conversation.objects.create()
    return redirect('chat:conversation', pk=conversation.pk)


def conversation_view(request, pk):
    """View a conversation and chat interface."""
    conversation = get_object_or_404(Conversation, pk=pk)
    messages = conversation.messages.all()
    voice_members = VoiceMember.objects.filter(is_active=True)

    context = {
        'conversation': conversation,
        'messages': messages,
        'conversations': Conversation.objects.all()[:10],
        'voice_members': voice_members,
    }
    return render(request, 'chat/conversation.html', context)


@require_http_methods(["POST"])
def conversation_delete(request, pk):
    """Delete a conversation."""
    conversation = get_object_or_404(Conversation, pk=pk)
    conversation.delete()
    return redirect('chat:list')


@require_http_methods(["POST"])
def send_message(request, pk):
    """Send a message and get AI response."""
    conversation = get_object_or_404(Conversation, pk=pk)
    user_message = request.POST.get('message', '').strip()

    if not user_message:
        return HttpResponse("Message required", status=400)

    # Save user message
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content=user_message,
    )

    # Generate title if first message
    if conversation.messages.count() == 1:
        conversation.generate_title()

    # Check if streaming is requested
    if request.htmx:
        return _stream_response(conversation, user_message)
    else:
        return _sync_response(conversation, user_message)


def _sync_response(conversation: Conversation, user_message: str) -> HttpResponse:
    """Generate a synchronous response."""
    try:
        # Get conversation history
        history = _get_conversation_history(conversation)

        # Query RAG pipeline with optional voice translation
        response, chunks = rag_pipeline.query_with_voice(
            question=user_message,
            conversation_history=history,
            voice_member=conversation.voice,
            voice_blend=conversation.voice_blend,
            stream=False,
        )

        # Build sources
        sources = _chunks_to_sources(chunks)

        # Save assistant message
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=response,
            sources=sources,
        )

        return redirect('chat:conversation', pk=conversation.pk)

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=f"Sorry, I encountered an error: {str(e)}",
        )
        return redirect('chat:conversation', pk=conversation.pk)


def _stream_response(conversation: Conversation, user_message: str) -> StreamingHttpResponse:
    """Generate a streaming response for HTMX."""

    def generate():
        try:
            # Get conversation history
            history = _get_conversation_history(conversation)

            # Query RAG pipeline with streaming and optional voice translation
            response_gen, chunks = rag_pipeline.query_with_voice(
                question=user_message,
                conversation_history=history,
                voice_member=conversation.voice,
                voice_blend=conversation.voice_blend,
                stream=True,
            )

            # Collect full response
            full_response = ""

            for chunk in response_gen:
                full_response += chunk
                # Send SSE event
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            # Build sources
            sources = _chunks_to_sources(chunks)

            # Save assistant message
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=full_response,
                sources=sources,
            )

            # Send completion event with sources
            yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=error_msg,
            )
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    response = StreamingHttpResponse(
        generate(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def _get_conversation_history(conversation: Conversation) -> list[dict]:
    """Get conversation history as list of message dicts."""
    messages = conversation.messages.exclude(
        pk=conversation.messages.last().pk if conversation.messages.exists() else None
    )
    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]


@require_http_methods(["POST"])
def conversation_set_voice(request, pk):
    """Set the voice for a conversation."""
    conversation = get_object_or_404(Conversation, pk=pk)

    voice_id = request.POST.get('voice_id')
    blend = request.POST.get('blend') == 'true'

    if blend:
        conversation.voice = None
        conversation.voice_blend = True
    elif voice_id:
        member = get_object_or_404(VoiceMember, pk=voice_id, is_active=True)
        conversation.voice = member
        conversation.voice_blend = False
    else:
        conversation.voice = None
        conversation.voice_blend = False

    conversation.save()
    return redirect('chat:conversation', pk=conversation.pk)


def _chunks_to_sources(chunks) -> list[dict]:
    """Convert retrieved chunks to source dicts."""
    sources = []
    seen = set()

    for chunk in chunks:
        key = (chunk.source_title, chunk.source_url)
        if key not in seen:
            seen.add(key)
            sources.append({
                'title': chunk.source_title,
                'url': chunk.source_url,
                'type': chunk.source_type,
            })

    return sources


@csrf_exempt
@require_http_methods(["POST"])
def groupme_query(request):
    """GroupMe bot API endpoint. Requires Bearer token auth via Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    expected = settings.API_SECRET_KEY
    if not expected or not auth_header.startswith('Bearer ') or auth_header[7:] != expected:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    groupme_id = data.get('groupme_id', '').strip()
    text = data.get('text', '').strip()

    if not text:
        return JsonResponse({'error': 'text is required'}, status=400)

    try:
        response, _chunks = rag_pipeline.query(question=text, stream=False)
        return JsonResponse({'groupme_id': groupme_id, 'response': response})
    except Exception as e:
        logger.error(f"groupme_query error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
