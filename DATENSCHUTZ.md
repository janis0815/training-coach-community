# Datenschutzerklärung — Training Coach Community Bot

## Was wird gespeichert?

- Dein Name und Telegram-Chat-ID
- Deine Sportarten, Uhr-Typ und Einstellungen
- Trainingspläne und Leistungsdaten die du eingibst
- Suunto/Strava-Tokens (für automatischen Datenabruf)
- Schlaf- und Recovery-Daten (wenn Suunto-Webhooks aktiv)
- Gesprächsverlauf (wird bei /reset gelöscht)
- Feedback (wenn du /feedback nutzt)

## Wer hat Zugriff?

Nur der Bot-Betreiber. Deine Daten werden nicht an Dritte weitergegeben. Die KI (Groq) sieht deine Daten nur während der Planberechnung — nichts wird dort dauerhaft gespeichert.

## Drittanbieter

- **Groq**: Verarbeitet deine Nachrichten für die KI-Antworten. Keine dauerhafte Speicherung.
- **Suunto/Strava**: Nur wenn du dich verbindest. Du kannst die Verbindung jederzeit trennen.
- **Open-Meteo**: Wetterdaten basierend auf deiner PLZ (keine persönlichen Daten übermittelt).
- **rad-net.de**: Rad-Events basierend auf deiner PLZ (keine persönlichen Daten übermittelt).
- **Render**: Hosting-Anbieter. Server in der EU.

## Hosting

Der Bot läuft auf Render (kostenloser Plan). Bei Inaktivität schläft der Server ein — die erste Antwort kann dann bis zu 50 Sekunden dauern.

## Deine Rechte

- `/export` — Alle deine Daten als JSON herunterladen
- `/delete BESTÄTIGEN` — Alle deine Daten unwiderruflich löschen
- `/reset` — Gesprächsverlauf löschen

## Kontakt

Bei Fragen wende dich direkt an den Bot-Betreiber.
