# API Key Wrapper

Minimal Django app for unified chat and image generation with per-user API keys and optional 2FA.

## Setup

1. Create a virtual environment and install dependencies:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in the shared provider keys:

```
cp .env.example .env
```

3. Run migrations and create a superuser:

```
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
- Static files are collected to `staticfiles/` and served by Django fallback routing if no reverse proxy static alias is configured.

## Enable 2FA

1. Log in.
2. Go to **Account** and click **Enable 2FA**.
3. Scan the QR code in Google Authenticator, then enter the code to confirm.

## Shared API Keys

API keys are loaded from `.env` and shared by all users.
The **API Keys** page is read-only and shows which provider env vars are configured.

## Chat models

The app defaults to GLM-5.2 for chat and GLM-Image for image generation. The Chat page auto-detects configured providers from `.env`; if GLM is not configured, it falls back to another configured provider. A provider's built-in default chat models become selectable when its provider key is present:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `GLM_API_KEY`
- `KIMI_API_KEY`

You can add model IDs without changing code:

```bash
DEEPSEEK_CHAT_MODELS=deepseek-chat=DeepSeek Chat,deepseek-reasoner=DeepSeek Reasoner
ANTHROPIC_CHAT_MODELS=claude-sonnet-4-20250514=Claude Sonnet 4
GLM_CHAT_MODELS=glm-5.2=GLM-5.2,glm-5=GLM-5
KIMI_CHAT_MODELS=moonshot-v1-8k=Kimi 8K,moonshot-v1-32k=Kimi 32K
CHAT_MODELS=anthropic:claude-custom=Claude Custom,deepseek:deepseek-custom=DeepSeek Custom
```

Restart the app after changing `.env`:

```bash
bash start_server.sh restart
```

Admins can rename or hide chat models in Django admin under **Provider models**. If a display name is blank, the app falls back to the default label or a title-cased model ID.

## Nano Banana image studio

The Image page supports:

- Nano Banana 2, Nano Banana Pro, and the original Nano Banana
- Model-specific aspect ratios and output resolutions
- Generate and reference-image edit modes
- Upload, paste, or drag-and-drop references
- Prompt starters, edit-again actions, and image downloads

Set `GLM_API_KEY` in `.env`, then restart the server. GLM-Image is the default image model and uses a 60-second provider timeout by default because its HD requests can take around 20 seconds. Set `GLM_IMAGE_REQUEST_TIMEOUT_SECONDS` to adjust it. Nano Banana remains available with `NANO_BANANA_API_KEY` or `GOOGLE_API_KEY`. Image model IDs and allowed output settings live in `api_key_wrapper/gateway/model_catalog.py`.

## Account creation

Public signup is disabled. Existing users can continue signing in. Administrators create users at `/admin/`; the admin form supports an initial credit load.

## Simple CI/CD

`.github/workflows/deploy.yml` runs the tests and deploys every push to `main`.

Add these repository secrets under **GitHub → Settings → Secrets and variables → Actions**:

- `VM_HOST`: VM hostname or IP address
- `VM_USER`: SSH user
- `VM_SSH_KEY`: private SSH key used to access the VM
- `VM_APP_PATH`: checkout path on the VM, such as `/opt/llm-wrapper`

The matching public key must be in the VM user's `~/.ssh/authorized_keys`. The VM checkout must already have its production `.env`, `venv`, and access to pull the repository. After that, a push to `main` automatically runs tests, pulls the new commit on the VM, installs requirements, runs migrations, collects static files, and restarts Gunicorn.

To deploy manually on the VM:

```bash
cd /opt/llm-wrapper
git pull --ff-only origin main
venv/bin/pip install -r requirements.txt
bash start_server.sh restart
```


## Notes

- All app pages require login and confirmed 2FA.
- Image generation/editing is synchronous for now (no background jobs).
- Usage billing uses credits for image and text requests.
- Only admins can view usage ledger/wallet and add load credits via Django admin.
- Add rate limiting (e.g., django-ratelimit) before exposing the API publicly.
