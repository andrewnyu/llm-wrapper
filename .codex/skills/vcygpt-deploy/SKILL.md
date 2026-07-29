---
name: vcygpt-deploy
description: Deploy, restart, or verify the VCY GPT Django app at chat.vcygpt.org. Use when asked to SSH into the production VM, check whether code/static files/migrations are applied, restart Gunicorn, investigate stale UI, or deploy changes for this llm-wrapper project.
---

# VCY GPT Deploy

## Production Target

- Host: `root@chat.vcygpt.org`
- Live checkout: `/var/www/llm-wrapper`
- Public site: `https://chat.vcygpt.org`
- Process manager: project-local `bash start_server.sh`
- Gunicorn port: `0.0.0.0:8000`

Do not deploy or restart from `/root/llm-wrapper`. That path was disabled after causing stale UI confusion. Treat `/var/www/llm-wrapper` as the source of truth.

## Verify State

Use SSH with noninteractive options:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 root@chat.vcygpt.org 'cd /var/www/llm-wrapper && git rev-parse --short HEAD && git status --short --branch && bash start_server.sh status'
```

For stale UI or static asset bugs, also check:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 root@chat.vcygpt.org 'cd /var/www/llm-wrapper && grep -n "v=" templates/chat/chat.html templates/imaging/image.html && ls -la staticfiles/chat staticfiles/imaging'
```

If port conflicts appear, inspect the actual listener:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 root@chat.vcygpt.org 'ss -ltnp sport = :8000 || true && ps -eo pid,ppid,lstart,cmd | grep -E "gunicorn|manage.py|runserver" | grep -v grep'
```

## Deploy Latest Main

When the user asks to deploy or confirms production changes:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 root@chat.vcygpt.org 'cd /var/www/llm-wrapper && git pull --ff-only origin main && bash start_server.sh restart'
```

The restart script runs migrations and `collectstatic`, then starts Gunicorn and writes logs to `/var/www/llm-wrapper/logs/gunicorn.log`.

## Post-Deploy Checks

After restart, verify all of these:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 root@chat.vcygpt.org 'cd /var/www/llm-wrapper && git rev-parse --short HEAD && bash start_server.sh status && tail -n 60 logs/gunicorn.log'
```

Then use browser or HTTP checks as appropriate:

```bash
curl -I https://chat.vcygpt.org/
curl -I https://chat.vcygpt.org/static/chat/chat.css
```

For authenticated UI concerns, use the browser only if a logged-in session is available; otherwise report that the public login page is reachable and server/static checks passed.

## Known Cleanup

If `collectstatic` prints duplicate Django admin static warnings, check for an untracked source directory:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 root@chat.vcygpt.org 'cd /var/www/llm-wrapper && git status --short && test ! -d static/admin || echo "static/admin duplicate source exists"'
```

It is safe to remove `/var/www/llm-wrapper/static/admin` when it is untracked and only duplicating Django's admin assets. Do not remove `staticfiles/admin`; that is collected output.
