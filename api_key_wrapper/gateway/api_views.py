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
    image_request_credits,
)

from .key_resolver import get_api_key_for_provider
from .model_catalog import (
    DEFAULT_IMAGE_ASPECT_RATIO,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_IMAGE_RESOLUTION,
    get_chat_model,
    get_image_model,
)
from .providers.registry import get_provider_client

DEFAULT_IMAGE_FEEDBACK_PROMPT = (
    "Analyze this image and respond in 3 sections: "
    "(1) Brief description. "
    "(2) Spelling/text issues you can read, with suggested corrections. "
    "(3) Practical feedback and improvements."
)
MAX_IMAGE_PROMPT_CHARS = 2000


def _image_options(payload):
    model_id = payload.get("model") or DEFAULT_IMAGE_MODEL
    if not isinstance(model_id, str):
        return None, _json_error("model must be a string")
    model_id = model_id.strip()
    model = get_image_model(model_id)
    if not model:
        return None, _json_error("Unsupported image model")

    aspect_ratio = payload.get("aspect_ratio") or DEFAULT_IMAGE_ASPECT_RATIO
    if not isinstance(aspect_ratio, str):
        return None, _json_error("aspect_ratio must be a string")
    aspect_ratio = aspect_ratio.strip()
    if aspect_ratio not in model["aspect_ratios"]:
        return None, _json_error("Unsupported aspect ratio for this image model")

    image_size = payload.get("image_size") or DEFAULT_IMAGE_RESOLUTION
    if not isinstance(image_size, str):
        return None, _json_error("image_size must be a string")
    image_size = image_size.strip().upper()
    if image_size not in model["resolutions"]:
        return None, _json_error("Unsupported resolution for this image model")

    return {
        "provider": model["provider"],
        "model": model_id,
        "model_label": model["label"],
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
    }, None


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


def _check_image_credits(user):
    wallet = get_or_create_wallet(user)
    required = image_request_credits()
    if wallet.balance_credits < required:
        return _json_insufficient(required, wallet.balance_credits)
    return None


def _parse_json_payload(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        if not isinstance(payload, dict):
            return None, _json_error("JSON body must be an object")
        return payload, None
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
    if not get_chat_model(provider, model):
        return _json_error("Unsupported provider or model")

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
    if not isinstance(prompt, str) or not prompt.strip():
        return _json_error("prompt is required")
    prompt = prompt.strip()
    if len(prompt) > MAX_IMAGE_PROMPT_CHARS:
        return _json_error(f"prompt exceeds max length ({MAX_IMAGE_PROMPT_CHARS})")
    options, options_error = _image_options(payload)
    if options_error:
        return options_error
    provider = options["provider"]

    credit_error = _check_image_credits(request.user)
    if credit_error:
        return credit_error

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
                **options,
            },
        )
    except NotImplementedError as exc:
        return _json_error(str(exc), status=501)
    except Exception as exc:
        message = "Provider request failed"
        if settings.DEBUG:
            return _json_error(f"{message}: {exc}", status=502)
        return _json_error(message, status=502)

    try:
        wallet, _usage_event, charged_credits = charge_image_request(
            user=request.user,
            feature="image_generate",
            metadata={**options, "source": "gateway_api"},
        )
    except InsufficientCreditsError:
        fresh_wallet = get_or_create_wallet(request.user)
        return _json_insufficient(image_request_credits(), fresh_wallet.balance_credits)

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
        settings=options,
    )

    return JsonResponse(
        {
            "images": result.images,
            "text": result_text,
            "job_id": job.id,
            "settings": options,
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
    if not isinstance(prompt, str) or not prompt.strip():
        return _json_error("prompt is required")
    prompt = prompt.strip()
    if len(prompt) > MAX_IMAGE_PROMPT_CHARS:
        return _json_error(f"prompt exceeds max length ({MAX_IMAGE_PROMPT_CHARS})")
    if not isinstance(input_image, str) or not input_image:
        return _json_error("input_image is required")
    options, options_error = _image_options(payload)
    if options_error:
        return options_error
    model_config = get_image_model(options["model"])
    if not model_config.get("supports_edit", False):
        return _json_error("This image model does not support reference-image edits")
    provider = options["provider"]

    credit_error = _check_image_credits(request.user)
    if credit_error:
        return credit_error

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
                **options,
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

    try:
        wallet, _usage_event, charged_credits = charge_image_request(
            user=request.user,
            feature="image_edit",
            metadata={**options, "source": "gateway_api"},
        )
    except InsufficientCreditsError:
        fresh_wallet = get_or_create_wallet(request.user)
        return _json_insufficient(image_request_credits(), fresh_wallet.balance_credits)

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
        settings=options,
    )

    return JsonResponse(
        {
            "images": result.images,
            "text": result_text,
            "job_id": job.id,
            "settings": options,
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

    raw_prompt = payload.get("prompt") or ""
    if not isinstance(raw_prompt, str):
        return _json_error("prompt must be a string")
    prompt = raw_prompt.strip()
    if len(prompt) > MAX_IMAGE_PROMPT_CHARS:
        return _json_error(f"prompt exceeds max length ({MAX_IMAGE_PROMPT_CHARS})")
    input_image = payload.get("input_image")
    provider = "nano_banana"

    if not isinstance(input_image, str) or not input_image:
        return _json_error("input_image is required")

    final_prompt = prompt or DEFAULT_IMAGE_FEEDBACK_PROMPT

    credit_error = _check_image_credits(request.user)
    if credit_error:
        return credit_error

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

    try:
        wallet, _usage_event, charged_credits = charge_image_request(
            user=request.user,
            feature="image_feedback",
            metadata={"provider": provider, "source": "gateway_api"},
        )
    except InsufficientCreditsError:
        fresh_wallet = get_or_create_wallet(request.user)
        return _json_insufficient(image_request_credits(), fresh_wallet.balance_credits)

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
