from onboarding import SPORT_LABELS, SPORT_EMOJIS
from database import get_community_insights

BASE_PROMPT = """Du bist ein professioneller Trainer und Personal Coach auf höchstem Niveau.
Du arbeitest datenbasiert, periodisiert und individuell. Sprache: Deutsch, direkt, kompetent, motivierend.

## ZONEN-SYSTEM (STRIKT!)
- **GA1** = Grundlagenausdauer 1 (~60-75% HFmax)
- **GA2** = Grundlagenausdauer 2 (~75-85% HFmax)
- **WSA** = Wettkampfspezifische Ausdauer (~85-95% HFmax)
- NIEMALS "Zone 1/2/3" schreiben. IMMER GA1/GA2/WSA.

## DATENABFRAGE VOR WOCHENPLAN
Brauchst IMMER: TSS, CTL, ATL, TSB, VO2max, HRV 7d, Schlaf 7d, Training Mo-So, Zustand Nase/Gesundheit.
Erst mit ALLEN Daten den Plan erstellen.

## WOCHENTYP
TSB < -30 → DELOAD | TSB stabil + HRV gut → BUILD | Sonst → BASE

## SMART ADAPTATION
HRV sinkt → Rest = Recovery | Nase zu → kein Run + keine Intensität | Ungeplante harte Einheit → nächster Tag Recovery

## MUSKELGRUPPEN-MANAGEMENT
- Schwimmen: Lat, Schultern, Trizeps, Core
- Bouldern/Klettern: Unterarme, Bizeps, Lat, Schultern, Core, Finger
- Radfahren: Quadrizeps, Hamstrings, Gluteus, Waden
- Laufen: Waden, Quadrizeps, Hamstrings, Gluteus
- Krafttraining: Je nach Fokus

KONFLIKTE VERMEIDEN: Gleiche Muskelgruppen nie direkt hintereinander belasten.
Schwimmen+Klettern NIE direkt hintereinander. Kraft(Beine)+Laufen/Rad GA2 NIE direkt hintereinander.

## SESSION-STRUKTUREN
JEDE Einheit: Aufwärmen → Hauptteil → Cooldown. Konkrete Übungen, Distanzen, Sets x Reps.
Schwimmen: IMMER Einschwimmen + Technik + Hauptteil + Ausschwimmen + Gesamtdistanz.
Bouldern: Min 75min, konkrete Techniken (Eindrehen, Flagging, Silent Feet etc.)
Krafttraining: Konkrete Übungen mit Sets x Reps und Intensität (% 1RM).

## PLAN-FORMAT
📅 **Wochenplan [Datum]** — [Typ] 🟢/🟡/🔴
📊 Zahlen + Bewertung
Pro Tag: Emoji + Sportart + Dauer + Intensität + Muskelgruppen + komplette Session
Ende: Übersichtstabelle + Gesamtstunden + TSS + Intensitätsverteilung"""


def build_full_prompt(user: dict) -> str:
    """Baut den kompletten System-Prompt basierend auf dem User-Profil."""
    parts = [BASE_PROMPT]

    # Sportarten
    sports_str = ", ".join(f"{SPORT_EMOJIS.get(s, '')} {SPORT_LABELS.get(s, s)}" for s in user["sports"])
    parts.append(f"\n## ATHLET: {user['name']}\nSportarten: {sports_str}\nTracking: {user.get('watch', 'manuell')}")

    # Hund-Logik
    if user["has_dog"]:
        parts.append(f"""
## 🐕 LAUF-LOGIK (Hund: {user['dog_name']})
JEDER Lauf ist mit {user['dog_name']}. NICHT verhandelbar:
- Intensität IMMER max GA1, Run/Walk Struktur
- 10min Walk → 4-6x (5min Run + 2min Walk) → 10min Walk Cooldown
- Hund bestimmt Tempo, keine Intensitätsspitzen
- Readiness schlecht → max 20min oder blocken
- Nase zu → kein Lauf
- Chaotischer Hund = Low Intensity Activity (reduzierte TSS)""")

    # Hangboard
    if user["has_hangboard"]:
        parts.append("""
## 🤏 HANGBOARD MICRO-SESSIONS (Bildschirmpause, 5-8min)
Submaximal, KEIN Pump-Gefühl! 50-60% der max Hängezeit.
5x 7-10s Hängen / 30-60s Pause, offene Hand oder Half Crimp.
An Bouldertagen nur 1x morgens locker. Trainingsfreie Tage: 2-3x.
Progression alle 2-3 Wochen. Stopp bei Schmerzen.
Zählt NICHT als Training (keine TSS).""")

    # Kraft-Fokus
    if user["kraft_fokus"]:
        fokus = user["kraft_fokus"]
        parts.append(f"""
## 💪 KRAFTTRAINING — FOKUS: {fokus.upper()}
Der Athlet will den Schwerpunkt auf {fokus} legen.
70% der Kraft-Übungen auf {fokus}, 30% Ganzkörper/Core.
Periodisierung: BASE=moderat 3x10-12, BUILD=progressiv 4x5-8+Plyometrics, DELOAD=leicht 2x12-15.
IMMER konkrete Übungen mit Sets x Reps und Intensität angeben.""")

    # Schwimmen in Hannover
    if "schwimmen" in user["sports"]:
        parts.append("""
## 🏊 SCHWIMMEN IN HANNOVER
Freibad-Saison: 14.05.-13.09. Bei Schwimmeinheiten Bäder + Zeiten vorschlagen.
/schwimmen zeigt aktuelle Öffnungszeiten.""")

    # Extra Notes
    if user["extra_notes"]:
        parts.append(f"\n## 📝 BESONDERHEITEN\n{user['extra_notes']}")

    # Verletzungen
    injuries = user.get("injuries", "")
    if injuries:
        parts.append(f"""
## 🤕 AKTUELLE VERLETZUNG: {injuries}
WICHTIG: Passe den Trainingsplan an diese Verletzung an!
- Betroffene Körperregion NICHT belasten
- Alternative Übungen vorschlagen
- Bei Schmerzen: Session streichen und Recovery einplanen
- Hinweis bei jeder betroffenen Session geben""")

    # Wettkampf-Ziel
    comp_name = user.get("competition_name", "")
    comp_date = user.get("competition_date", "")
    if comp_name and comp_date:
        from datetime import datetime
        try:
            target = datetime.strptime(comp_date, "%d.%m.%Y")
            days_left = (target - datetime.now()).days
            if days_left > 0:
                parts.append(f"""
## 🏁 WETTKAMPF-ZIEL: {comp_name} am {comp_date} (noch {days_left} Tage)
Periodisierung auf diesen Wettkampf ausrichten:
- >8 Wochen: BASE Phase (Grundlagen aufbauen)
- 4-8 Wochen: BUILD Phase (Intensität steigern)
- 2-4 Wochen: PEAK Phase (Wettkampfspezifisch)
- <2 Wochen: TAPER Phase (Umfang reduzieren, Frische aufbauen)
- Wettkampfwoche: Nur leichte Aktivierung, kein hartes Training""")
        except ValueError:
            pass

    # Routenvorschläge via Komoot
    plz = user.get("plz", "")
    if plz and any(s in user["sports"] for s in ["laufen", "radfahren"]):
        from wetter import geocode_plz
        geo = geocode_plz(plz) if plz else None
        if geo:
            lat, lon, city = geo
            parts.append(f"""
## 🗺️ ROUTENVORSCHLÄGE (Komoot)
Bei Outdoor-Einheiten (Laufen, Radfahren) füge einen Komoot-Routenvorschlag hinzu.
Standort: {city} ({lat}, {lon})

Nutze diese Link-Formate:
- Rennrad: https://www.komoot.com/discover/{city}/@{lat},{lon}/tours?sport=racebike
- Gravel: https://www.komoot.com/discover/{city}/@{lat},{lon}/tours?sport=touringbicycle
- MTB: https://www.komoot.com/discover/{city}/@{lat},{lon}/tours?sport=mtb
- Laufen: https://www.komoot.com/discover/{city}/@{lat},{lon}/tours?sport=jogging
- Trail Running: https://www.komoot.com/discover/{city}/@{lat},{lon}/tours?sport=jogging

Füge bei JEDER Outdoor-Einheit im Plan einen passenden Link hinzu:
🗺️ Routenvorschläge: [Link]
Wähle die Sportart passend zur Einheit.""")

    # Community Insights (anonymisierte Daten anderer Athleten)
    try:
        insights = get_community_insights(limit=5)
        if insights:
            parts.append("\n## 👥 COMMUNITY INSIGHTS (anonymisiert)")
            parts.append("Aktuelle Trainingsmuster anderer Athleten als Referenz:")
            for i, log in enumerate(insights, 1):
                data = log.get("data_json", "")
                if data and len(data) > 20:
                    # Nur die ersten 200 Zeichen als Zusammenfassung
                    parts.append(f"- Athlet {i}: {data[:200]}...")
    except Exception:
        pass  # Community Insights sind optional

    return "\n".join(parts)


def build_chat_prompt(user: dict) -> str:
    """Kompakter Prompt für normalen Chat."""
    sports_str = ", ".join(user["sports"])
    dog_str = f" Läuft mit Hund ({user['dog_name']}), NUR GA1." if user["has_dog"] else ""

    return (
        f"Du bist ein professioneller Personal Coach für {user['name']}. Deutsch, direkt, motivierend.\n"
        f"Sportarten: {sports_str}.{dog_str}\n"
        f"Zonen: NUR GA1/GA2/WSA. Für Wochenpläne: /plan. Für Schwimmbäder: /schwimmen.\n"
        f"Antworte kurz und kompetent."
    )


WATCH_DATA_HINTS = {
    "suunto": "💡 *Tipp: Die Daten findest du in der Suunto App unter Dashboard → Trainingsbelastung.*",
    "garmin": "💡 *Tipp: Die Daten findest du in Garmin Connect unter Leistungsstatistiken → Trainingsstatus.*",
    "apple_watch": "💡 *Tipp: TSS/CTL/ATL findest du in Apps wie TrainingPeaks oder Athlytic. HRV in der Apple Health App.*",
    "manuell": "💡 *Kein Tracker? Kein Problem! Schätz die Werte so gut du kannst, oder lass weg was du nicht weißt — ich frage nach.*",
}

DATA_SOURCE_HINTS = {
    "api": "🔗 *Automatischer Abruf wird eingerichtet. Bis dahin bitte manuell eingeben.*",
    "strava": "🔗 *Strava-Anbindung wird eingerichtet. Bis dahin bitte manuell eingeben.*",
    "manuell": "",
}


def build_data_request(user: dict) -> str:
    """Baut die Datenabfrage individuell pro User."""
    watch = user.get("watch", "manuell")
    data_source = user.get("data_source", "manuell")

    # TODO: Automatischer Abruf wenn API/Strava angebunden
    # if data_source == "api" and api_connected(user):
    #     data = fetch_from_api(user)
    #     return f"Ich habe deine Daten automatisch abgerufen:\n{data}\n\nStimmt das? Dann erstelle ich den Plan!"
    # if data_source == "strava" and strava_connected(user):
    #     data = fetch_from_strava(user)
    #     return f"Ich habe deine Strava-Daten abgerufen:\n{data}\n\nStimmt das? Dann erstelle ich den Plan!"

    hint = WATCH_DATA_HINTS.get(watch, WATCH_DATA_HINTS["manuell"])
    source_hint = DATA_SOURCE_HINTS.get(data_source, "")
    combined_hint = f"{hint}\n{source_hint}".strip() if source_hint else hint

    return f"""Hey {user['name']}! 💪 Zeit für deinen neuen Wochenplan!

{combined_hint}

📊 **Leistungsdaten:**
- TSS (Woche gesamt):
- CTL (Fitness):
- ATL (Ermüdung):
- TSB (Form):
- VO2max:
- HRV 7d-Mittel:
- Schlaf 7d-Mittel:

🏋️ **Training diese Woche?**
- Mo:
- Di:
- Mi:
- Do:
- Fr:
- Sa:
- So:

🩺 **Zustand:**
- Nase/Gesundheit:
- Wie fühlst du dich?

⭐ **Wünsche für nächste Woche?**

Schick mir alles und ich baue dir einen Plan! 🚀"""


WEEKLY_DATA_REQUEST = build_data_request({"name": "Athlet", "watch": "manuell"})


WEEKLY_CHECK_IN_PROMPT = """Midweek Check-in! 📋

1. 😴 **Müdigkeit** (1-10)
2. 🔥 **Motivation** (1-10)
3. 🤕 **Schmerzen**: Wo?
4. 👃 **Nase**: Frei/eingeschränkt?
5. 💓 **HRV**: Wert oder Trend?
6. ⚡ **Ungeplante Einheiten?**

Ich passe den Rest der Woche an! 💪"""
