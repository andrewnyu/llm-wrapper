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
```

3. Run migrations and create a superuser:

```
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

4. Start the server:

```
python manage.py runserver
```

## Enable 2FA

1. Log in.
2. Go to **Account** and click **Enable 2FA**.
3. Scan the QR code in Google Authenticator, then enter the code to confirm.

## Add API Keys

1. Go to **API Keys**.
2. Click **Add API Key** and enter the provider and key.

Keys are stored in plaintext for this MVP. Replace this with encrypted storage before production.

## Nano Banana integration

The stub client is in `api_key_wrapper/gateway/providers/nano_banana.py`.
Replace the placeholder endpoint URL and response parsing with the real API details.

## Notes

- All pages require login.
- Image generation is synchronous for now (no background jobs).
- Add rate limiting (e.g., django-ratelimit) before exposing the API publicly.
