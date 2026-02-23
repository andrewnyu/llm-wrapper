# API Key Wrapper

Minimal Django app for unified chat and image generation with per-user API keys and optional 2FA.

## Setup

1. Create a virtual environment and install dependencies:

```
python3 -m venv .venv
source .venv/bin/activate
pip install 'django>=5,<6' pyotp qrcode pillow requests
```

2. Create `.env` from the example values:

```
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_SESSION_COOKIE_SECURE=0
DJANGO_CSRF_COOKIE_SECURE=0
API_REQUEST_TIMEOUT_SECONDS=20
USAGE_IMAGE_REQUEST_CREDITS=1.0
USAGE_TEXT_CREDITS_PER_1K_TOKENS=0.25
USAGE_ESTIMATED_CHARS_PER_TOKEN=4
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
NANO_BANANA_API_KEY=
CUSTOM_API_KEY=
```

3. Run migrations and create a superuser:

```
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

4. Start the server in production mode (background):

```
bash start_server.sh start
```

Useful process commands:

```
bash start_server.sh status
bash start_server.sh stop
bash start_server.sh restart
```

Production requirements:
- Set `DJANGO_DEBUG=0`
- Set a strong `DJANGO_SECRET_KEY`
- Set `DJANGO_ALLOWED_HOSTS` (comma-separated)
- Install Gunicorn in your venv (`pip install gunicorn`)

## Enable 2FA

1. Log in.
2. Go to **Account** and click **Enable 2FA**.
3. Scan the QR code in Google Authenticator, then enter the code to confirm.

## Shared API Keys

API keys are loaded from `.env` and shared by all users.
The **API Keys** page is read-only and shows which provider env vars are configured.

## Nano Banana integration

The stub client is in `api_key_wrapper/gateway/providers/nano_banana.py`.
Replace the placeholder endpoint URL and response parsing with the real API details.

## Notes

- All pages require login.
- Image generation/editing is synchronous for now (no background jobs).
- Usage billing uses credits for image and text requests.
- Only admins can view usage ledger/wallet and add load credits via Django admin.
- Add rate limiting (e.g., django-ratelimit) before exposing the API publicly.
