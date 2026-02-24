import json
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse

from api_key_wrapper.chat.models import Conversation, Message
from api_key_wrapper.imaging.models import ImageJob
from api_key_wrapper.usage.services import (
    InsufficientCreditsError,
    charge_image_request,
    charge_text_tokens,
    credits_for_text_tokens,
    estimate_tokens_from_text,
    extract_token_usage,
    get_or_create_wallet,
)

from .key_resolver import get_api_key_for_provider
from .providers.registry import get_provider_client

DEFAULT_IMAGE_FEEDBACK_PROMPT = (
    "Analyze this image and respond in 3 sections: "
    "(1) Brief description. "
    "(2) Spelling/text issues you can read, with suggested corrections. "
    "(3) Practical feedback and improvements."
)


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


def _parse_json_payload(request):
    try:
        return json.loads(request.body.decode("utf-8")), None
    except RequestDataTooBig:
        return None, _json_error("Upload too large. Please use a smaller image.", status=413)
    except json.JSONDecodeError:
        return None, _json_error("Invalid JSON")


@login_required
def chat_complete(request):
    if request.method != "POST":
        return _json_error("Only POST allowed", status=405)

    payload, payload_error = _parse_json_payload(request)
    if payload_error:
        return payload_error

    provider = payload.get("provider")
    model = payload.get("model")
    messages = payload.get("messages", [])
    temperature = payload.get("temperature")
    session_id = payload.get("session_id")

    if not provider or not model or not messages:
        return _json_error("provider, model, and messages are required")

    wallet = get_or_create_wallet(request.user)
    min_required = credits_for_text_tokens(1)
    if wallet.balance_credits < min_required:
        return _json_insufficient(min_required, wallet.balance_credits)

    try:
        api_key = get_api_key_for_provider(provider)
    except ValueError as exc:
        return _json_error(str(exc), status=403)

    try:
        client = get_provider_client(provider)
        result = client.chat_complete(
            api_key,
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
        session = Conversation.objects.filter(id=session_id, user=request.user).first()

    if not session:
        title = next((m.get("content") for m in messages if m.get("role") == "user"), "New Chat")
        title = (title or "New Chat")[:60]
        session = Conversation.objects.create(
            user=request.user,
            title=title,
        )

    latest_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if latest_user:
        Message.objects.create(
            conversation=session,
            role="user",
            content=latest_user.get("content", ""),
            model=model,
        )

    usage_tokens = extract_token_usage(result.usage)
    input_text = "\n".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
    output_text = result.text or ""
    token_count_for_charge = usage_tokens
    if usage_tokens is None:
        usage_tokens = estimate_tokens_from_text(input_text, output_text)
        token_count_for_charge = None

    try:
        wallet, _usage_event, charged_credits = charge_text_tokens(
            user=request.user,
            feature="chat_complete",
            token_count=token_count_for_charge,
            input_text=input_text,
            output_text=output_text,
            reference_id=str(session.id),
            metadata={"provider": provider, "model": model, "source": "gateway_api"},
        )
    except InsufficientCreditsError:
        fresh_wallet = get_or_create_wallet(request.user)
        required = credits_for_text_tokens(usage_tokens)
        return _json_insufficient(required, fresh_wallet.balance_credits)

    Message.objects.create(
        conversation=session,
        role="assistant",
        content=result.text,
        model=model,
        token_count=usage_tokens,
    )

    return JsonResponse(
        {
            "text": result.text,
            "usage": result.usage,
            "raw": result.raw,
            "session_id": session.id,
            "usage_charged": str(charged_credits),
            "remaining_credits": str(wallet.balance_credits),
        }
    )


@login_required
def image_generate(request):
    if request.method != "POST":
        return _json_error("Only POST allowed", status=405)

    payload, payload_error = _parse_json_payload(request)
    if payload_error:
        return payload_error

    prompt = payload.get("prompt")
    size = payload.get("size", "1024x1024")
    n = payload.get("n", 1)
    provider = "nano_banana"

    if not prompt:
        return _json_error("prompt is required")

    try:
        wallet, _usage_event, charged_credits = charge_image_request(
            user=request.user,
            feature="image_generate",
            metadata={"provider": provider, "source": "gateway_api"},
        )
    except InsufficientCreditsError:
        fresh_wallet = get_or_create_wallet(request.user)
        return _json_insufficient("1.0000", fresh_wallet.balance_credits)

    try:
        api_key = get_api_key_for_provider(provider)
    except ValueError as exc:
        return _json_error(str(exc), status=403)

    try:
        client = get_provider_client(provider)
        result = client.image_generate(
            api_key,
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

    result_text = (result.text or "").strip()
    job = ImageJob.objects.create(
        user=request.user,
        prompt=prompt,
        provider=provider,
        kind=ImageJob.KIND_STUDIO,
        status="success",
        result_text=result_text,
        result_urls=[
            image.get("url") or image.get("base64")
            for image in result.images
            if image.get("url") or image.get("base64")
        ],
    )

    return JsonResponse(
        {
            "images": result.images,
            "text": result_text,
            "job_id": job.id,
            "usage_charged": str(charged_credits),
            "remaining_credits": str(wallet.balance_credits),
        }
    )


@login_required
def image_edit(request):
    if request.method != "POST":
        return _json_error("Only POST allowed", status=405)

    payload, payload_error = _parse_json_payload(request)
    if payload_error:
        return payload_error

    prompt = payload.get("prompt")
    input_image = payload.get("input_image")
    provider = "nano_banana"

    if not prompt:
        return _json_error("prompt is required")
    if not input_image:
        return _json_error("input_image is required")

    try:
        wallet, _usage_event, charged_credits = charge_image_request(
            user=request.user,
            feature="image_edit",
            metadata={"provider": provider, "source": "gateway_api"},
        )
    except InsufficientCreditsError:
        fresh_wallet = get_or_create_wallet(request.user)
        return _json_insufficient("1.0000", fresh_wallet.balance_credits)

    try:
        api_key = get_api_key_for_provider(provider)
    except ValueError as exc:
        return _json_error(str(exc), status=403)

    try:
        client = get_provider_client(provider)
        result = client.image_edit(
            api_key,
            {
                "prompt": prompt,
                "input_image": input_image,
            },
        )
    except NotImplementedError as exc:
        return _json_error(str(exc), status=501)
    except ValueError as exc:
        return _json_error(str(exc), status=400)
    except Exception as exc:
        message = "Provider request failed"
        if settings.DEBUG:
            return _json_error(f"{message}: {exc}", status=502)
        return _json_error(message, status=502)

    result_text = (result.text or "").strip()
    job = ImageJob.objects.create(
        user=request.user,
        prompt=prompt,
        provider=provider,
        kind=ImageJob.KIND_STUDIO,
        status="success",
        result_text=result_text,
        result_urls=[
            image.get("url") or image.get("base64")
            for image in result.images
            if image.get("url") or image.get("base64")
        ],
    )

    return JsonResponse(
        {
            "images": result.images,
            "text": result_text,
            "job_id": job.id,
            "usage_charged": str(charged_credits),
            "remaining_credits": str(wallet.balance_credits),
        }
    )


@login_required
def image_feedback(request):
    if request.method != "POST":
        return _json_error("Only POST allowed", status=405)

    payload, payload_error = _parse_json_payload(request)
    if payload_error:
        return payload_error

    prompt = (payload.get("prompt") or "").strip()
    input_image = payload.get("input_image")
    provider = "nano_banana"

    if not input_image:
        return _json_error("input_image is required")

    final_prompt = prompt or DEFAULT_IMAGE_FEEDBACK_PROMPT

    try:
        wallet, _usage_event, charged_credits = charge_image_request(
            user=request.user,
            feature="image_feedback",
            metadata={"provider": provider, "source": "gateway_api"},
        )
    except InsufficientCreditsError:
        fresh_wallet = get_or_create_wallet(request.user)
        return _json_insufficient("1.0000", fresh_wallet.balance_credits)

    try:
        api_key = get_api_key_for_provider(provider)
    except ValueError as exc:
        return _json_error(str(exc), status=403)

    try:
        client = get_provider_client(provider)
        result = client.image_edit(
            api_key,
            {
                "prompt": final_prompt,
                "input_image": input_image,
            },
        )
    except NotImplementedError as exc:
        return _json_error(str(exc), status=501)
    except ValueError as exc:
        return _json_error(str(exc), status=400)
    except Exception as exc:
        message = "Provider request failed"
        if settings.DEBUG:
            return _json_error(f"{message}: {exc}", status=502)
        return _json_error(message, status=502)

    result_text = (result.text or "").strip()
    job = ImageJob.objects.create(
        user=request.user,
        prompt=prompt or "Image feedback",
        provider=provider,
        kind=ImageJob.KIND_FEEDBACK,
        status="success",
        result_text=result_text,
        result_urls=[
            image.get("url") or image.get("base64")
            for image in result.images
            if image.get("url") or image.get("base64")
        ],
    )

    return JsonResponse(
        {
            "images": result.images,
            "text": result_text,
            "job_id": job.id,
            "usage_charged": str(charged_credits),
            "remaining_credits": str(wallet.balance_credits),
        }
    )
