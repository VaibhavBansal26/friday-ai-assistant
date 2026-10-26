# Friday AI Assistant

Friday is a privacy-conscious desktop AI assistant for macOS. It combines a React/Tauri desktop interface with a local FastAPI service, realtime voice, approval-gated external actions, coding tools, communications, content workflows, learning tools, and local memory foundations.

> Friday is designed to show evidence for completed actions. High-impact operations such as sending email, publishing content, creating repositories, pushing Git commits, or submitting forms require explicit approval.

## Capabilities

| Area | What Friday can do | Setup required |
| --- | --- | --- |
| Voice and conversation | Realtime speech, transcription, spoken responses, tool routing, startup greeting | OpenAI API key, microphone permission |
| Tasks and planning | Create and manage tasks, learning topics, study plans, ideas, and notifications | None for local/in-memory use |
| Gmail | Connect Gmail, sync recent messages, summarize mail, create visible drafts, and send after approval | Google OAuth client and Gmail API |
| Spotify | Open Spotify, search for a track, select a Spotify Connect device, and play music | Spotify Premium and Spotify OAuth app |
| GitHub and coding | List and clone repositories, inspect trees, read/create/edit files, open Finder or VS Code, run safe commands, create repositories, commit/push with approval | GitHub CLI authentication; VS Code CLI for editor actions |
| LinkedIn content | Create copyable drafts, preview publishing, and publish through an approved connected application | LinkedIn developer application and approved products/scopes |
| Content studio | Draft LinkedIn, Medium, X, Instagram, and other channel content in visible workspaces | Publishing credentials vary by provider |
| Video studio | Create YouTube Shorts project/storyboard data and local video workflows | Rendering/upload provider configuration for final delivery |
| Browser and device | Read allowlisted pages, prepare form-fill previews, open approved URLs/apps, and require approval before submission | Playwright browsers and macOS permissions |
| Files and attachments | Upload images, videos, and documents; work only inside configured file roots | Configure authorized roots |
| Jobs and resume | Resume parsing/tailoring foundations, job matching, application drafts, and review gates | Resume/profile data supplied locally; provider availability varies |
| Memory and knowledge | Facts, projects, ideas, proposed memories, retrieval, QMD-style search, and provenance | PostgreSQL recommended for persistence |
| Safety and verification | Risk levels, approvals, credential isolation, redaction, audit events, and provider evidence | Enabled by default |

Detailed architecture and operability status are in [`docs/architecture/BLUEPRINT.md`](docs/architecture/BLUEPRINT.md) and [`docs/architecture/OPERABILITY_MATRIX.md`](docs/architecture/OPERABILITY_MATRIX.md).

## Requirements

- macOS (the desktop wrapper and local device actions currently target macOS)
- Python 3.11 or newer
- Node.js 20 or newer and npm
- Rust stable toolchain
- [Tauri v2 prerequisites](https://v2.tauri.app/start/prerequisites/)
- Docker Desktop (optional, recommended for PostgreSQL and Redis)
- GitHub CLI (`gh`) and Visual Studio Code CLI (`code`) for coding integrations
- Spotify desktop app for local playback

## Quick start

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/friday-ai-assistant.git
cd friday-ai-assistant
cp .env.example .env.local

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e 'apps/api[dev]'

cd apps/desktop
npm install
cd ../..
```

Optionally start persistent services:

```bash
docker compose up -d postgres redis
```

Run the API in terminal 1:

```bash
source .venv/bin/activate
uvicorn friday.main:app --app-dir apps/api/src --host 127.0.0.1 --port 8000 --reload
```

Run the desktop interface in terminal 2:

```bash
cd apps/desktop
npm run tauri dev
```

The packaged macOS app starts its local API automatically when built from this checkout.

## Core configuration

Edit `.env.local` and set only the providers you intend to use:

```dotenv
FRIDAY_ENV=development
FRIDAY_USER_DISPLAY_NAME=User
FRIDAY_GITHUB_OWNER=
FRIDAY_PERSISTENCE_BACKEND=memory
FRIDAY_REQUIRE_LOCAL_SESSION=true
FRIDAY_ENABLE_MODEL_CALLS=true
FRIDAY_MODEL_DEFAULT=gpt-4.1-mini
FRIDAY_MODEL_REALTIME=gpt-realtime-2.1
OPENAI_API_KEY=
FRIDAY_AUTHORIZED_FILE_ROOTS=.
FRIDAY_ALLOWED_BROWSER_DOMAINS=linkedin.com,github.com
FRIDAY_BROWSER_HEADLESS=false
```

Use `FRIDAY_PERSISTENCE_BACKEND=memory` for evaluation. For durable data, start Docker services and select the database-backed mode supported by the persistence layer. Local OAuth tokens and generated user data are stored under ignored `artifacts/` paths and must never be committed.

## OpenAI voice and models

1. Create an OpenAI API key in your own project.
2. Add it only to `.env.local` as `OPENAI_API_KEY`.
3. Set `FRIDAY_ENABLE_MODEL_CALLS=true`.
4. Keep `FRIDAY_MODEL_REALTIME=gpt-realtime-2.1`, or choose a Realtime model available to your project.
5. Open Friday and grant microphone access in **System Settings → Privacy & Security → Microphone**.

If conversation shows **Load failed**, verify `http://127.0.0.1:8000/v1/health`. In a packaged build, close older Friday instances before opening the newest app.

## GitHub and coding

```bash
brew install gh
gh auth login
gh auth status
```

Optionally set `FRIDAY_GITHUB_OWNER`. If blank, Friday discovers the username from `gh api user`.

Friday can list repositories, clone an account-owned repository into `artifacts/repositories/`, visualize an authorized repository, read/create/edit text files, run allowlisted test/build/lint commands, open Finder or VS Code, and request approval for repository creation and Git pushes. It verifies the remote commit after a push.

Set `FRIDAY_AUTHORIZED_FILE_ROOTS` to the smallest directories required. Repository creation, external pushes, and similar high-impact actions remain approval-gated.

## Gmail

1. Create or select a project in Google Cloud Console.
2. Enable the **Gmail API**.
3. Configure the OAuth consent screen. During testing, add each permitted Google account as a test user.
4. Create an OAuth client compatible with the loopback callback.
5. Register `http://127.0.0.1:8000/v1/oauth/gmail/callback`.
6. Configure:

   ```dotenv
   FRIDAY_GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
   FRIDAY_GMAIL_REDIRECT_URI=http://127.0.0.1:8000/v1/oauth/gmail/callback
   ```

7. Open Friday, choose **Connect Gmail**, and finish Google authorization.

Friday requests identity, Gmail read, compose, and send scopes. Drafting is local and visible; actual sending requires approve-once authorization. If your OAuth client requires a secret, enter it through Friday's local setup flow; never commit it.

## Spotify

1. Create an app in the Spotify Developer Dashboard.
2. Register `http://127.0.0.1:8000/v1/oauth/spotify/callback`.
3. Configure:

   ```dotenv
   FRIDAY_SPOTIFY_CLIENT_ID=your-spotify-client-id
   FRIDAY_SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/v1/oauth/spotify/callback
   ```

4. Connect Spotify from Friday.
5. Keep Spotify open and select this Mac once in Spotify's device picker if no active Connect device is found.

Playback control requires Spotify Premium. Friday uses PKCE, so a Spotify client secret is not stored.

## LinkedIn

1. Create a LinkedIn developer app associated with a page you administer.
2. Request the products/scopes needed for sign-in and posting. LinkedIn approval determines which publishing features work.
3. Register `http://127.0.0.1:8000/v1/oauth/linkedin/callback` for local development.
4. Configure:

   ```dotenv
   FRIDAY_LINKEDIN_CLIENT_ID=your-client-id
   FRIDAY_LINKEDIN_CLIENT_SECRET=your-client-secret
   FRIDAY_LINKEDIN_REDIRECT_URI=http://127.0.0.1:8000/v1/oauth/linkedin/callback
   FRIDAY_LINKEDIN_AUTHOR_URN=
   ```

5. Connect LinkedIn in Friday. Create a visible draft, inspect it, request publishing approval, and only then publish.

The `infrastructure/linkedin-oauth-relay/` example is for hosted callback experiments. Configure your own host and never commit provider secrets.

## Browser, files, and macOS permissions

Install the browser runtime if needed:

```bash
source .venv/bin/activate
playwright install chromium
```

Grant only the permissions you need in **System Settings → Privacy & Security**:

- Microphone: realtime voice
- Accessibility/Automation: approved control of supported desktop apps
- Files and Folders: user-selected directories

Browser reads are limited by `FRIDAY_ALLOWED_BROWSER_DOMAINS`. Form filling produces a preview; submission requires explicit approval. Keep password and payment fields user-controlled.

## Content, Medium, X, and YouTube

- Draft generation creates visible, copyable content records.
- LinkedIn publishing requires approved LinkedIn OAuth products/scopes.
- Medium does not currently provide a generally available new integration-token flow; use draft/export workflows unless you already have supported credentials.
- X publishing requires a write-enabled X developer project and OAuth credentials; none are included here.
- YouTube Shorts currently create structured vertical-video project data. Final rendering/upload requires a renderer/provider and YouTube OAuth; uploads should remain approval-gated.

A generated draft or storyboard is not proof of publication. Friday marks external actions complete only when provider evidence is returned.

## Build the macOS app

```bash
cd apps/desktop
npm run tauri build
```

Outputs appear under `apps/desktop/src-tauri/target/release/bundle/`.

The current native startup hook expects this checkout's `.venv` and API source to remain available. A fully standalone public installer should bundle a Python/API sidecar and add Apple signing and notarization.

## Tests

```bash
source .venv/bin/activate
pytest apps/api/tests
ruff check apps/api/src apps/api/tests

cd apps/desktop
npm test
npm run build
```

Before every public push, inspect exactly what is staged:

```bash
git status --short
git diff --cached --stat
git grep -n -I -E '(OPENAI_API_KEY=.+|CLIENT_SECRET=.+|Bearer [A-Za-z0-9_-]{20,})' --cached
```

## Privacy and security

- Real secrets belong in `.env.local`, macOS Keychain, or the ignored credential vault—not source control.
- This mixed local workspace is ignored by default; only application source/configuration paths are allowlisted.
- OAuth tokens, uploads, resumes, browser profiles, generated media, cloned repositories, memory stores, and user content are excluded.
- Models receive scoped tools and credential references, not plaintext credentials.
- External writes require policy approval and provider evidence.
- Always review staged files before pushing publicly.

## Troubleshooting

| Problem | Check |
| --- | --- |
| `Load failed` | Ensure the API listens on port 8000; close stale Friday instances and reopen the current build |
| Voice does not listen | Grant microphone access, select the Mac microphone, and verify Realtime model access/API billing |
| Gmail 403 | Add the account as an OAuth test user or publish/verify the consent app as appropriate |
| Gmail authorization failed | Confirm client ID, client secret if required, callback URI, Gmail API, and scopes |
| Spotify 502/no playback | Reconnect OAuth, use Premium, open Spotify, and choose an active Connect device |
| GitHub unavailable | Run `gh auth status`; reauthenticate with repository permissions |
| VS Code does not open | Install the `code` shell command from VS Code's Command Palette |
| File operation rejected | Add the directory to `FRIDAY_AUTHORIZED_FILE_ROOTS`; protected `.env` files remain blocked |
| LinkedIn publishing rejected | Confirm the callback, approved products/scopes, page role, and token validity |

## Project structure

```text
apps/api/                 FastAPI service, agents, adapters, and tests
apps/desktop/             React + Tauri macOS application
docs/architecture/        Architecture, operability, and completion audits
infrastructure/postgres/  Database bootstrap schema
infrastructure/linkedin-oauth-relay/  Optional callback relay example
```

## Responsible use

Friday can act on email, repositories, browsers, files, and social platforms when connected. Keep approval gates enabled, grant minimum permissions, inspect generated content, and never publish or send sensitive information without review.
