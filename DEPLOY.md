# Deployment auf Render — Schritt für Schritt

## Vorbereitung

1. Erstelle ein GitHub-Repository und pushe den Code (OHNE `.env`)
2. Erstelle einen Account auf https://render.com (kostenlos mit GitHub)

## Service erstellen

1. Render Dashboard → "New +" → "Web Service"
2. Verbinde dein GitHub-Repo
3. Einstellungen:
   - Name: `training-coach-community`
   - Region: `Frankfurt (EU Central)`
   - Runtime: `Docker`
   - Plan: `Free`

## Umgebungsvariablen

Unter "Environment" alle Keys eintragen:

| Key | Value | Woher? |
|-----|-------|--------|
| `GROQ_API_KEY` | Dein Key | https://console.groq.com |
| `TELEGRAM_BOT_TOKEN` | Dein Token | @BotFather in Telegram |
| `STRAVA_CLIENT_ID` | Deine ID | https://www.strava.com/settings/api |
| `STRAVA_CLIENT_SECRET` | Dein Secret | https://www.strava.com/settings/api |
| `SUUNTO_CLIENT_ID` | Deine ID | https://apizone.suunto.com/profile |
| `SUUNTO_CLIENT_SECRET` | Dein Secret | https://apizone.suunto.com/profile |
| `SUUNTO_SUBSCRIPTION_KEY` | Dein Key | https://apizone.suunto.com/profile |
| `OAUTH_BASE_URL` | `https://DEIN-SERVICE.onrender.com` | Render Dashboard |
| `OAUTH_HOST` | `0.0.0.0` | Immer so |
| `OAUTH_PORT` | `5000` | Immer so |
| `REQUIRE_HTTPS` | `true` | Immer so |

## Nach dem ersten Deploy

1. Kopiere deine Render-URL (z.B. `https://training-coach-community.onrender.com`)
2. Trag sie als `OAUTH_BASE_URL` in den Render Env-Vars ein
3. Bei Suunto API Zone: Redirect URI auf `https://DEINE-URL.onrender.com/suunto/callback`
4. Bei Strava API Settings: Authorization Callback Domain auf `DEINE-URL.onrender.com` (nur Domain, ohne https://)

## Fertig!

Teste mit `/start` in Telegram.

## Gut zu wissen

- Render Free Tier schläft nach Inaktivität ein — erste Antwort kann bis zu 50 Sekunden dauern
- SQLite-Datenbank wird bei Redeploy zurückgesetzt (Render hat kein persistentes Filesystem im Free Tier)
- Für persistente Daten: Render Disk oder externe DB (z.B. Supabase Free Tier)
