# Deployment auf Render — Schritt für Schritt

## Vorbereitung

1. Erstelle ein GitHub-Repository für den Community-Bot
2. Pushe den Code dahin (OHNE die `.env`-Datei — die ist in `.gitignore`)

## Auf Render deployen

### Schritt 1: Account erstellen
- Geh zu https://render.com
- Klick "Get Started for Free"
- Melde dich mit deinem GitHub-Account an

### Schritt 2: Neuen Service erstellen
- Klick oben rechts auf "New +"
- Wähle "Web Service"
- Verbinde dein GitHub-Repository
- Wähle das Repository mit dem Community-Bot aus

### Schritt 3: Service konfigurieren
- Name: `training-coach-community` (oder was du willst)
- Region: `Frankfurt (EU Central)` (am nächsten zu dir)
- Branch: `main`
- Runtime: `Docker` (wird automatisch erkannt wegen Dockerfile)
- Instance Type: `Free`

### Schritt 4: Umgebungsvariablen setzen
Klick auf "Environment" und füge diese Variablen hinzu:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | Dein Groq API Key |
| `TELEGRAM_BOT_TOKEN` | Dein Telegram Bot Token |
| `STRAVA_CLIENT_ID` | Deine Strava Client ID |
| `STRAVA_CLIENT_SECRET` | Dein Strava Client Secret |
| `SUUNTO_CLIENT_ID` | Deine Suunto Client ID |
| `SUUNTO_CLIENT_SECRET` | Dein Suunto Client Secret |
| `SUUNTO_SUBSCRIPTION_KEY` | Dein Suunto Subscription Key |
| `SUUNTO_WEBHOOK_SECRET` | Dein Suunto Webhook Secret |
| `OAUTH_BASE_URL` | `https://training-coach-community.onrender.com` |
| `OAUTH_HOST` | `0.0.0.0` |
| `OAUTH_PORT` | `5000` |
| `REQUIRE_HTTPS` | `true` |

(Den OAUTH_BASE_URL bekommst du nach dem ersten Deploy — das ist die URL die Render dir gibt)

### Schritt 5: Deploy starten
- Klick "Create Web Service"
- Warte bis der Build fertig ist (dauert 2-3 Minuten)
- Wenn grün: Dein Bot läuft!

### Schritt 6: OAuth-URLs aktualisieren
Nachdem du die Render-URL hast (z.B. `https://training-coach-community.onrender.com`):

1. Geh zu Suunto API Zone → Profile → OAuth Settings
   - Ändere Redirect URI zu: `https://training-coach-community.onrender.com/suunto/callback`
2. Geh zu Strava API Settings
   - Ändere Redirect URI zu: `https://training-coach-community.onrender.com/strava/callback`
3. Aktualisiere auf Render die Umgebungsvariable `OAUTH_BASE_URL` auf deine Render-URL

## Fertig!

Dein Bot läuft jetzt 24/7 auf Render mit HTTPS. Teste mit `/start` in Telegram.

## Wichtig zu wissen

- Render Free Tier: Der Service schläft nach 15 Min Inaktivität ein und braucht ~30 Sek zum Aufwachen
- Die SQLite-Datenbank wird bei jedem Redeploy zurückgesetzt (Render hat kein persistentes Filesystem im Free Tier)
- Für persistente Daten: Render Disk ($0.25/GB/Monat) oder externe DB (z.B. Supabase Free Tier)
