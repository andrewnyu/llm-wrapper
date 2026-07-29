import json
import logging
import threading
import time
import uuid
from collections import deque

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .llm import DEFAULT_MODEL, DEFAULT_PROVIDER, generate_stream
from .models import Conversation, Message
from api_key_wrapper.gateway.key_resolver import is_provider_configured
from api_key_wrapper.gateway.model_catalog import get_chat_model, serialize_chat_models
from api_key_wrapper.usage.services import (
    InsufficientCreditsError,
    charge_text_tokens,
    credits_for_text_tokens,
    estimate_tokens_from_text,
    get_or_create_wallet,
)

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 8000
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 60

_ACTIVE_GENERATIONS = {}
_ACTIVE_LOCK = threading.Lock()


def _json_error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _json_insufficient(required_credits, remaining_credits):
    return JsonResponse(
        {
            "error": "Insufficient credits",
            "required_credits": str(required_credits),
            "remaining_credits": str(remaining_credits),
        },
        status=402,
    )


def _parse_json(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def _get_request_user(request):
    return request.user if request.user.is_authenticated else None


def _user_filter_kwargs(request):
    user = _get_request_user(request)
    if user is None:
        return {"user__isnull": True}
    return {"user": user}


def _serialize_conversation(conversation):
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "createdAt": conversation.created_at.isoformat(),
        "updatedAt": conversation.updated_at.isoformat(),
    }


def _serialize_message(message):
    return {
        "id": str(message.id),
        "conversationId": str(message.conversation_id),
        "role": message.role,
        "content": message.content,
        "createdAt": message.created_at.isoformat(),
        "model": message.model or None,
        "tokenCount": message.token_count,
    }


def _sse(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _check_rate_limit(request):
    history = deque(request.session.get("chat_rate_history", []), maxlen=100)
    now = int(time.time())
    while history and now - history[0] > RATE_LIMIT_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= RATE_LIMIT_REQUESTS:
        request.session["chat_rate_history"] = list(history)
        request.session.modified = True
        return False
    history.append(now)
    request.session["chat_rate_history"] = list(history)
    request.session.modified = True
    return True


@login_required
def chat_view(request):
    return render(
        request,
        "chat/chat.html",
        {
            "chat_models": serialize_chat_models(),
            "default_provider": DEFAULT_PROVIDER,
            "default_model": DEFAULT_MODEL,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def conversations_view(request):
    user_filters = _user_filter_kwargs(request)
    if request.method == "GET":
        conversations = Conversation.objects.filter(**user_filters).order_by("-updated_at")
        return JsonResponse({"items": [_serialize_conversation(item) for item in conversations]})

    payload = _parse_json(request)
    if payload is None:
        return _json_error("Invalid JSON")

    title = (payload.get("title") or "New chat").strip()[:120] or "New chat"
    conversation = Conversation.objects.create(
        user=_get_request_user(request),
        title=title,
    )
    return JsonResponse(_serialize_conversation(conversation), status=201)


def _conversation_for_request_or_404(request, conversation_id):
    user_filters = _user_filter_kwargs(request)
    return get_object_or_404(Conversation, id=conversation_id, **user_filters)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def conversation_detail_view(request, conversation_id):
    conversation = _conversation_for_request_or_404(request, conversation_id)
    if request.method == "DELETE":
        conversation.delete()
        return JsonResponse({"ok": True})

    payload = _parse_json(request)
    if payload is None:
        return _json_error("Invalid JSON")
    title = (payload.get("title") or "").strip()[:120]
    if not title:
        return _json_error("title is required")
    conversation.title = title
    conversation.save(update_fields=["title", "updated_at"])
    return JsonResponse(_serialize_conversation(conversation))


@login_required
@require_http_methods(["GET", "POST"])
def conversation_messages_view(request, conversation_id):
    conversation = _conversation_for_request_or_404(request, conversation_id)
    if request.method == "GET":
        messages = conversation.messages.order_by("created_at")
        return JsonResponse({"items": [_serialize_message(item) for item in messages]})

    payload = _parse_json(request)
    if payload is None:
        return _json_error("Invalid JSON")

    content = (payload.get("content") or "").strip()
    provider = (payload.get("provider") or DEFAULT_PROVIDER).strip()
    model = (payload.get("model") or DEFAULT_MODEL).strip()
    model_choice = get_chat_model(provider, model)
    if not model_choice:
        return _json_error("Unsupported provider or model")
    if not content:
        return _json_error("content is required")
    if len(content) > MAX_MESSAGE_CHARS:
        return _json_error(f"content exceeds max length ({MAX_MESSAGE_CHARS})")
    if not _check_rate_limit(request):
        return _json_error("rate limit exceeded, try again shortly", status=429)
    wallet = get_or_create_wallet(request.user)
    min_required = credits_for_text_tokens(1)
    if wallet.balance_credits < min_required:
        return _json_insufficient(min_required, wallet.balance_credits)
    if not is_provider_configured(provider):
        return _json_error(f"{model_choice['label']} is not configured on this server", status=403)

    is_first_message = not conversation.messages.exists()
    user_message = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=content,
    )
    if is_first_message and conversation.title in ("", "New chat", "New Chat"):
        conversation.title = content[:60].strip() or conversation.title
        conversation.save(update_fields=["title"])
    assistant_message = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content="",
        model=model,
    )
    conversation.save(update_fields=["updated_at"])

    request_id = str(uuid.uuid4())
    stop_event = threading.Event()
    with _ACTIVE_LOCK:
        _ACTIVE_GENERATIONS[request_id] = stop_event

    history = list(
        Message.objects.filter(conversation=conversation)
        .exclude(id=assistant_message.id)
        .order_by("created_at")
        .values("role", "content")
    )

    def event_stream():
        assistant_text = ""
        usage_charged = False
        try:
            yield _sse(
                "meta",
                {
                    "requestId": request_id,
                    "conversationId": str(conversation.id),
                    "messageId": str(assistant_message.id),
                    "provider": provider,
                    "model": model,
                    "modelLabel": model_choice["label"],
                    "title": conversation.title,
                },
            )

            token_stream = generate_stream(
                user=_get_request_user(request),
                messages=history,
                model=model,
                provider=provider,
            )
            try:
                for token in token_stream:
                    if stop_event.is_set():
                        break
                    if not token:
                        continue
                    assistant_text += token
                    yield _sse("delta", {"text": token})
            finally:
                close = getattr(token_stream, "close", None)
                if close:
                    close()

            final_text = assistant_text
            input_text = "\n".join(item.get("content", "") for item in history)
            wallet_obj = None
            token_count = None
            charged_credits = None
            try:
                wallet_obj, _usage_event, charged_credits = charge_text_tokens(
                    user=request.user,
                    feature="chat_stream",
                    token_count=None,
                    input_text=input_text,
                    output_text=final_text,
                    reference_id=str(conversation.id),
                    metadata={"provider": provider, "model": model, "source": "chat_stream"},
                )
                usage_charged = True
                token_count = _usage_event.unit_count
            except InsufficientCreditsError:
                Message.objects.filter(id__in=[user_message.id, assistant_message.id]).delete()
                fresh_wallet = get_or_create_wallet(request.user)
                required_tokens = estimate_tokens_from_text(input_text, final_text)
                required = credits_for_text_tokens(required_tokens)
                yield _sse(
                    "error",
                    {
                        "message": "Insufficient credits",
                        "requiredCredits": str(required),
                        "remainingCredits": str(fresh_wallet.balance_credits),
                    },
                )
                return

            assistant_message.content = final_text
            assistant_message.token_count = token_count
            assistant_message.save(update_fields=["content", "token_count"])
            conversation.save(update_fields=["updated_at"])

            yield _sse(
                "done",
                {
                    "fullText": final_text,
                    "title": conversation.title,
                    "usageCharged": str(charged_credits),
                    "remainingCredits": str(wallet_obj.balance_credits),
                },
            )
        except Exception:
            logger.exception("Chat generation failed")
            if usage_charged and assistant_text:
                assistant_message.content = assistant_text
                assistant_message.save(update_fields=["content"])
            else:
                Message.objects.filter(id__in=[user_message.id, assistant_message.id]).delete()
            yield _sse("error", {"message": "Failed to generate response"})
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_GENERATIONS.pop(request_id, None)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@login_required
@require_http_methods(["POST"])
def cancel_generate_view(request):
    payload = _parse_json(request)
    if payload is None:
        return _json_error("Invalid JSON")
    request_id = payload.get("requestId")
    if not request_id:
        return _json_error("requestId is required")

    with _ACTIVE_LOCK:
        stop_event = _ACTIVE_GENERATIONS.get(request_id)
    if stop_event:
        stop_event.set()
    return JsonResponse({"ok": True})
