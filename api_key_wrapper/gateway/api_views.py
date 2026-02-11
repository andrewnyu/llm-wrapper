import json
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse

from api_key_wrapper.chat.models import ChatMessage, ChatSession
from api_key_wrapper.imaging.models import ImageJob

from .models import ProviderKey
from .providers.registry import get_provider_client


def _json_error(message, status=400):
    return JsonResponse({"error": message}, status=status)


@login_required
def chat_complete(request):
    if request.method != "POST":
        return _json_error("Only POST allowed", status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return _json_error("Invalid JSON")

    provider = payload.get("provider")
    model = payload.get("model")
    messages = payload.get("messages", [])
    temperature = payload.get("temperature")
    session_id = payload.get("session_id")

    if not provider or not model or not messages:
        return _json_error("provider, model, and messages are required")

    try:
        key = ProviderKey.objects.filter(user=request.user, provider=provider).latest("created_at")
    except ProviderKey.DoesNotExist:
        return _json_error("Missing API key for provider. Add one on the API Keys page.", status=403)

    try:
        client = get_provider_client(provider)
        result = client.chat_complete(
            key.api_key,
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            },
        )
    except NotImplementedError as exc:
        return _json_error(str(exc), status=501)
    except Exception as exc:
        message = "Provider request failed"
        if settings.DEBUG:
            return _json_error(f"{message}: {exc}", status=502)
        return _json_error(message, status=502)

    session = None
    if session_id:
        session = ChatSession.objects.filter(id=session_id, user=request.user).first()

    if not session:
        title = next((m.get("content") for m in messages if m.get("role") == "user"), "New Chat")
        title = (title or "New Chat")[:60]
        session = ChatSession.objects.create(
            user=request.user,
            title=title,
            provider=provider,
            model=model,
        )

    latest_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if latest_user:
        ChatMessage.objects.create(
            session=session,
            role="user",
            content=latest_user.get("content", ""),
        )

    ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=result.text,
    )

    return JsonResponse(
        {
            "text": result.text,
            "usage": result.usage,
            "raw": result.raw,
            "session_id": session.id,
        }
    )


@login_required
def image_generate(request):
    if request.method != "POST":
        return _json_error("Only POST allowed", status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return _json_error("Invalid JSON")

    prompt = payload.get("prompt")
    size = payload.get("size", "1024x1024")
    n = payload.get("n", 1)
    provider = "nano_banana"

    if not prompt:
        return _json_error("prompt is required")

    try:
        key = ProviderKey.objects.filter(user=request.user, provider=provider).latest("created_at")
    except ProviderKey.DoesNotExist:
        return _json_error("Missing API key for Nano Banana. Add one on the API Keys page.", status=403)

    try:
        client = get_provider_client(provider)
        result = client.image_generate(
            key.api_key,
            {
                "prompt": prompt,
                "size": size,
                "n": n,
            },
        )
    except NotImplementedError as exc:
        return _json_error(str(exc), status=501)
    except Exception as exc:
        message = "Provider request failed"
        if settings.DEBUG:
            return _json_error(f"{message}: {exc}", status=502)
        return _json_error(message, status=502)

    job = ImageJob.objects.create(
        user=request.user,
        prompt=prompt,
        provider=provider,
        status="success",
        result_urls=[image.get("url") for image in result.images if image.get("url")],
    )

    return JsonResponse({"images": result.images, "job_id": job.id})
