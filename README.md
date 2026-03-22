# MusicKit MVP

MusicKit is a self-hosted Telegram Mini App that lets you search YouTube, download tracks as MP3, and play them through Navidrome on your own VPS.

## Stack

- `nginx`: reverse proxy and static Mini App
- `backend`: FastAPI API for Telegram auth, search, downloads, and protected file access
- `navidrome`: music player, playlists, favorites, library streaming
- `yt-dlp` + `ffmpeg`: search and audio extraction inside the backend container

## Folder Structure

```text
.
|-- .env.example
|-- .gitignore
|-- docker-compose.yml
|-- README.md
|-- backend
|   |-- Dockerfile
|   |-- requirements.txt
|   `-- app
|       |-- __init__.py
|       |-- auth.py
|       |-- config.py
|       |-- db.py
|       |-- dependencies.py
|       |-- main.py
|       |-- schemas.py
|       `-- services
|           |-- __init__.py
|           |-- navidrome.py
|           |-- telegram.py
|           `-- yt.py
|-- frontend
|   `-- index.html
`-- nginx
    `-- default.conf
```

## How It Works

1. Telegram opens the Mini App at `/`.
2. The frontend sends `initData` to `POST /api/auth/telegram`.
3. FastAPI validates the Telegram signature and issues an HTTP-only session cookie.
4. Nginx protects `/player/` with `auth_request` against FastAPI.
5. On approved requests Nginx forwards `Remote-User: tg_<telegram_id>` to Navidrome.
6. Navidrome external auth auto-creates the user and manages playlists, favorites, and streaming.
7. Search and downloads go through FastAPI, which saves MP3 files into `/music`.

## Setup

1. Install Docker Engine and Docker Compose Plugin on your Linux VPS.
2. Copy this project to the VPS.
3. Create your environment file:

   ```bash
   cp .env.example .env
   ```

4. Edit `.env`:
   - `APP_BASE_URL`: public HTTPS URL of the VPS, for example `https://music.example.com`
   - `TELEGRAM_BOT_TOKEN`: token from BotFather
   - `TELEGRAM_BOT_USERNAME`: bot username without `@`
   - `TELEGRAM_WEBAPP_URL`: same public URL that Telegram will open
   - `APP_SECRET_KEY`: long random secret for session signing
   - `JWT_COOKIE_SECURE=true` when running behind HTTPS
5. Make sure DNS for your domain points to the VPS.
6. Put TLS in front of Nginx before public use. A common production setup is Cloudflare Tunnel, Caddy, or a host-level Nginx with Let's Encrypt terminating HTTPS and forwarding to port `80`.
7. Start the full stack:

   ```bash
   docker compose up -d --build
   ```

8. Open `https://your-domain/` from your Telegram Mini App. The first authenticated Telegram user becomes the first Navidrome user, and Navidrome treats that user as admin on a fresh database.

## BotFather Setup

1. Open `@BotFather` in Telegram.
2. Run `/newbot` and complete the bot creation flow.
3. Save the token and set it in `.env` as `TELEGRAM_BOT_TOKEN`.
4. Run `/setmenubutton`.
5. Choose your bot.
6. Set the button text to `Open Player`.
7. Set the Web App URL to the same value as `TELEGRAM_WEBAPP_URL`, for example `https://music.example.com/`.
8. Optionally run `/setdescription` and `/setabouttext` so the bot explains what it does.

## Navidrome Notes

- Navidrome is mounted with `/music` backed by `./data/music`.
- Data and database are persisted in `./data/navidrome`.
- External authentication is enabled through the reverse proxy.
- Public registration is not exposed; users are created only when the proxy authenticates a Telegram session.
- Favorites, playlists, and streaming are handled in the native Navidrome UI at `/player/`.

## API Summary

- `POST /api/auth/telegram`: validate Telegram Mini App `initData` and create session
- `GET /api/me`: current Telegram user and recent downloads
- `GET /api/search?q=...`: search YouTube without downloading
- `POST /api/download`: download a selected YouTube result as MP3
- `GET /api/tracks/{source_id}/file`: download the stored MP3 file

## Production Notes

- Duplicate downloads are prevented by unique `source_id` tracking in the backend database.
- Search returns YouTube metadata only; downloads happen only after user confirmation.
- Navidrome rescans the library every minute, so imported tracks should appear quickly.
- Download progress is surfaced as a simple processing state in the UI, not a streaming progress bar.
- Related suggestions are seeded from recent downloads in a lightweight MVP-friendly way.

## One-Command Start

```bash
docker compose up -d --build
```
