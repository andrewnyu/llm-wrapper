from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction

from .models import UsageEvent, UsageWallet


FOUR_DECIMALS = Decimal("0.0001")


class InsufficientCreditsError(Exception):
    pass


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(FOUR_DECIMALS, rounding=ROUND_HALF_UP)


def _as_decimal(value) -> Decimal:
    return _quantize(Decimal(str(value)))


def estimate_tokens_from_text(*segments: str) -> int:
    chars_per_token = max(1, int(getattr(settings, "USAGE_ESTIMATED_CHARS_PER_TOKEN", 4)))
    total_chars = sum(len(segment or "") for segment in segments)
    if total_chars <= 0:
        return 1
    return max(1, (total_chars + chars_per_token - 1) // chars_per_token)


def credits_for_text_tokens(token_count: int) -> Decimal:
    token_count = max(1, int(token_count or 0))
    per_1k = _as_decimal(getattr(settings, "USAGE_TEXT_CREDITS_PER_1K_TOKENS", "0.25"))
    return _quantize((per_1k * Decimal(token_count)) / Decimal(1000))


def image_request_credits() -> Decimal:
    return _as_decimal(getattr(settings, "USAGE_IMAGE_REQUEST_CREDITS", "1.0"))


def extract_token_usage(usage) -> int | None:
    if not isinstance(usage, dict):
        return None

    for key in ("total_tokens", "totalTokens"):
        value = usage.get(key)
        if isinstance(value, int):
            return max(1, value)

    input_tokens = usage.get("prompt_tokens") or usage.get("promptTokens") or usage.get("input_tokens") or usage.get("inputTokens")
    output_tokens = usage.get("completion_tokens") or usage.get("completionTokens") or usage.get("output_tokens") or usage.get("outputTokens")
    if isinstance(input_tokens, int) or isinstance(output_tokens, int):
        return max(1, int(input_tokens or 0) + int(output_tokens or 0))
    return None


def get_or_create_wallet(user):
    wallet, _ = UsageWallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def load_credits(*, user, amount, created_by=None, metadata=None):
    amount_decimal = _as_decimal(amount)
    if amount_decimal <= 0:
        raise ValueError("load amount must be positive")

    wallet = UsageWallet.objects.select_for_update().get_or_create(user=user)[0]
    wallet.balance_credits = _quantize(wallet.balance_credits + amount_decimal)
    wallet.total_loaded_credits = _quantize(wallet.total_loaded_credits + amount_decimal)
    wallet.save(update_fields=["balance_credits", "total_loaded_credits", "updated_at"])

    event = UsageEvent.objects.create(
        user=user,
        event_type=UsageEvent.EVENT_LOAD,
        credits_delta=amount_decimal,
        unit_count=0,
        feature="admin_load",
        created_by=created_by,
        metadata=metadata or {},
    )
    return wallet, event


@transaction.atomic
def _charge(*, user, credits, event_type, unit_count, feature, reference_id="", metadata=None):
    credits_decimal = _as_decimal(credits)
    if credits_decimal <= 0:
        raise ValueError("charge amount must be positive")

    wallet = UsageWallet.objects.select_for_update().get_or_create(user=user)[0]
    if wallet.balance_credits < credits_decimal:
        raise InsufficientCreditsError(
            f"Insufficient credits: required={credits_decimal}, remaining={wallet.balance_credits}"
        )

    wallet.balance_credits = _quantize(wallet.balance_credits - credits_decimal)
    wallet.total_used_credits = _quantize(wallet.total_used_credits + credits_decimal)
    wallet.save(update_fields=["balance_credits", "total_used_credits", "updated_at"])

    event = UsageEvent.objects.create(
        user=user,
        event_type=event_type,
        credits_delta=_quantize(-credits_decimal),
        unit_count=max(0, int(unit_count or 0)),
        feature=feature or "",
        reference_id=reference_id or "",
        metadata=metadata or {},
    )
    return wallet, event, credits_decimal


def charge_image_request(*, user, feature, reference_id="", metadata=None):
    return _charge(
        user=user,
        credits=image_request_credits(),
        event_type=UsageEvent.EVENT_IMAGE_CONSUME,
        unit_count=1,
        feature=feature,
        reference_id=reference_id,
        metadata=metadata,
    )


def charge_text_tokens(
    *,
    user,
    feature,
    token_count=None,
    input_text="",
    output_text="",
    reference_id="",
    metadata=None,
):
    tokens = int(token_count or 0)
    estimated = False
    if tokens <= 0:
        tokens = estimate_tokens_from_text(input_text, output_text)
        estimated = True

    credits = credits_for_text_tokens(tokens)
    event_metadata = dict(metadata or {})
    event_metadata.update({"token_count": tokens, "token_estimated": estimated})
    return _charge(
        user=user,
        credits=credits,
        event_type=UsageEvent.EVENT_TEXT_CONSUME,
        unit_count=tokens,
        feature=feature,
        reference_id=reference_id,
        metadata=event_metadata,
    )
