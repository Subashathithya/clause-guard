# Release checklist

The runbook for shipping ClauseGuard: what to set, what to run, and how to
prove the release works before it reaches users. Everything here has been
exercised in this repository; the commands are copy-pasteable.

- [0. Before you start](#0-before-you-start)
- [1. Backend (Render)](#1-backend-render)
- [2. Frontend (Vercel)](#2-frontend-vercel)
- [3. Prove the release](#3-prove-the-release)
- [4. Android app](#4-android-app)
- [5. Monitoring](#5-monitoring)
- [6. Backup and restore](#6-backup-and-restore)
- [7. Rollback](#7-rollback)
- [8. Known gaps](#8-known-gaps)

---

## 0. Before you start

```bash
# Backend
cd backend
python -m venv venv && venv/Scripts/activate      # Windows
pip install -r requirements.txt
python -m pytest -q                                 # expect 90 passed

# Frontend
cd ../frontend
npm ci
npx tsc --noEmit
npm test -- --watchAll=false                       # expect 21 passed
npm run build
python scripts/check_i18n_keys.py                  # expect OK
```

The release is green only when every command above passes. The numbers in
brackets are the current counts; update them when the suite grows.

## 1. Backend (Render)

1. **Push the code.** The API is deployed from `render.yaml` (Render Blueprint),
   so the blueprint is the source of truth for the service definition.
2. **Set the environment variables** in the Render dashboard:

   | Variable | Value |
   |---|---|
   | `GROQ_API_KEY` | your Groq key (secret) |
   | `JWT_SECRET` | generated (Render "generateValue") |
   | `ALLOWED_ORIGINS` | `https://your-frontend.example` (comma-separated) |
   | `APP_ENV` | `production` (set by the blueprint) |
   | `REQUIRE_AUTH` | `true` (set by the blueprint) |
   | `DATABASE_URL` | free tier: a Neon Postgres string · paid tier: `sqlite:////app/data/persist/clauseguard.sqlite3` |
   | `CHROMA_DIR` | free tier: `/tmp/chroma_db` (rebuilt at startup) · paid tier: `/app/data/persist/chroma_db` |

   The blueprint already sets `APP_ENV=production`, `REQUIRE_AUTH=true` and
   generates `JWT_SECRET`. `ALLOWED_ORIGINS` must be filled in by hand — the
   API **refuses to start** without it.
3. **Deploy.** The build log ends with `CORS origins: …` and
   `Production posture verified (auth required, explicit origins).` If either
   line is missing, the deploy used the wrong environment.
4. **Seed the demo workspace once** (Render Shell → Settings → Shell):
   ```bash
   python scripts/seed_demo.py --reset
   ```
   This creates the demo account (`demo@clauseguard.app` / `Demo@12345`) and
   the sample contracts in both the guest and demo scopes.

## 2. Frontend (Vercel)

1. Import the repo with the root directory set to `frontend`.
2. `frontend/vercel.json` sets the build command, the output folder, the SPA
   rewrite and the cache headers for `index.html`, `service-worker.js` and
   `manifest.json`.
3. Set `REACT_APP_API_URL` to the deployed backend URL
   (`https://clauseguard-api.onrender.com`). The blueprint value in
   `vercel.json` is a working default — change it if you host the API
   elsewhere.
4. Deploy. The build output must include `service-worker.js`, `offline.html`
   and `manifest.json` at the site root.

## 3. Prove the release

Run these against the **deployed** backend:

```bash
API=https://clauseguard-api.onrender.com

# 1. It is alive and says what it is
curl -s $API/health | head -c 200

# 2. The docs are hidden in production
curl -s -o /dev/null -w "%{http_code}\n" $API/docs      # expect 404

# 3. Guest access is refused
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/analyze \
     -H "Content-Type: application/json" -d '{"text":"a contract that is long enough to pass the minimum length check for the api"}'
# expect 401

# 4. Only the configured origin is allowed
curl -s -D - -o /dev/null $API/health -H "Origin: https://your-frontend.example" \
     | grep -i "access-control-allow-origin"
# expect: access-control-allow-origin: https://your-frontend.example
curl -s -D - -o /dev/null $API/health -H "Origin: https://evil.example" \
     | grep -i "access-control-allow-origin"
# expect: (nothing)

# 5. Security headers are present
curl -s -D - -o /dev/null $API/health | grep -iE "x-content-type-options|x-frame-options|referrer-policy"
```

Then, in a browser:

- open the deployed frontend → the landing page renders;
- create an account → the dashboard shows **your** contracts (guest data is
  not visible to a signed-in account);
- analyze a short contract → the app asks for more text;
- open **Settings → Language** → switch to हिन्दி / தமிழ் / తెలుగు → the whole
  app follows;
- **Settings → This device → App lock** → on a device with a fingerprint or
  face, turn it on and confirm the app asks for it on the next open;
- turn off the network → open a page you already used → the app shell still
  loads and shows a clear "you are offline" notice.

## 4. Android app

```bash
cd frontend
npm run mobile:build          # builds against the production API, then cap sync
cd android
JAVA_HOME="/path/to/jdk" ./gradlew bundleRelease
# -> android/app/build/outputs/bundle/release/app-release.aab
```

- `npm run mobile:build` bakes `https://clauseguard-api.onrender.com` into the
  bundle, so a local address can never ship in the app.
- The release bundle is signed with `frontend/android/keystore.properties`
  (the keystore itself is git-ignored — keep a copy of it somewhere safe; losing
  it means you can never update the app on Play).
- Play Console needs: the app icon, a feature graphic, phone screenshots, the
  privacy policy (`frontend/public/privacy.html`) and a **Data safety** form that
  declares the contract text is uploaded for analysis and is not shared with
  third parties for advertising.
- Raise `versionCode` in `frontend/android/app/build.gradle` for every upload —
  Play rejects a re-used code.

## 5. Monitoring

| What | Tool | What to watch |
|---|---|---|
| Uptime | UptimeRobot (5-minute checks on `/health`) | The API answering at all |
| Errors | Render logs (the `clauseguard.errors` logger) | `Request failed [reference …]` lines — the reference id is also what the user sees |
| Usage | Render logs / `GET /stats` | Analyses per day, accounts created |
| Quota | `AUTH_RATE_LIMIT` responses (HTTP 429) | A spike means credential stuffing |

The error reference id is the link between a user's screenshot and the server
log: every failed request logs the same id it returns.

## 6. Backup and restore

```bash
cd backend
python scripts/backup_store.py                # -> data/backups/clauseguard-<stamp>.sqlite3
python scripts/backup_store.py --out /app/data/persist/backups --keep 14
```

The script uses SQLite's online backup API, so a copy taken while the API is
writing is still consistent. ChromaDB does not need backing up: it is rebuilt
from the relational rows and the fair-clause library.

**Restore:** stop the API, replace `data/clauseguard.sqlite3` with the backup
file, start the API again. The vector store rebuilds itself on startup.

Run the backup from the Render Shell or a scheduled job (Render cron jobs call
`python scripts/backup_store.py`); copy the files off the disk as well — a disk
on the same instance is not a backup.

## 7. Rollback

- **Frontend:** Vercel keeps every deployment — promote the previous one from
  the Deployments tab (instant).
- **Backend:** Render keeps the previous image — roll back from the Events tab,
  then re-run the seed if the release changed the data shape.
- **Android:** Play does not allow un-publishing a release to a subset of
  users. Ship a new build with a higher `versionCode` instead.

## 8. Known gaps

- The app lock is WebAuthn based; the Android build relies on the platform
  authenticator being available through the WebView. If it is not, the setting
  stays hidden rather than failing.
- The access token is kept in `localStorage`, so a script injection could read
  it. Moving it to an in-memory store with a session cookie is the next step.
- The sign-in rate limiter is in-memory per process: with several workers each
  keeps its own counters. Use Redis to share them.
- The translations were written by hand — a native-speaker review is worth
  doing before a regional launch.
- The offline shell is English only.
