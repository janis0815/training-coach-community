from datetime import date

FREIBAD_SAISON_START = date(2026, 5, 14)
FREIBAD_SAISON_ENDE = date(2026, 9, 13)

HALLENBAEDER = [
    {
        "name": "Anderter Bad",
        "adresse": "Eisteichweg 9, 30559 Hannover",
        "zeiten": {
            "Mo": "06:00-08:00",
            "Di": "06:00-08:00",
            "Mi": "06:00-08:00",
            "Do": "06:00-08:00 + 16:00-19:00",
            "Fr": "06:00-08:00",
            "Sa": "06:00-14:00",
            "So": "06:00-09:00",
        },
    },
    {
        "name": "Büntebad Hemmingen",
        "adresse": "Hohe Bünte 6, 30966 Hemmingen",
        "zeiten": {
            "Mo": "07:00-20:00",
            "Di": "07:00-20:00",
            "Mi": "07:00-20:00",
            "Do": "07:00-20:00",
            "Fr": "07:00-21:00",
            "Sa": "09:00-19:00",
            "So": "09:00-17:30",
        },
    },
    {
        "name": "Fössebad",
        "adresse": "Liepmannstraße 7B, 30453 Hannover",
        "zeiten": {
            "Mo": "06:00-18:00",
            "Di": "06:00-21:30",
            "Mi": "geschlossen (nur Kurse)",
            "Do": "06:00-18:00",
            "Fr": "06:00-18:00",
            "Sa": "08:00-18:00",
            "So": "09:00-15:00",
        },
    },
    {
        "name": "Misburger Bad (Kombibad)",
        "adresse": "Seckbruchstraße 18, 30629 Hannover",
        "zeiten": {
            "Mo": "06:30-21:30",
            "Di": "geschlossen",
            "Mi": "06:30-21:30",
            "Do": "06:30-18:00",
            "Fr": "06:30-18:00",
            "Sa": "09:00-21:30",
            "So": "10:00-19:00",
        },
    },
    {
        "name": "Nord-Ost-Bad",
        "adresse": "Podbielskistraße 301, 30655 Hannover",
        "zeiten": {
            "Mo": "Geschlossen (Sanierung bis Frühjahr 2027)",
            "Di": "Geschlossen (Sanierung bis Frühjahr 2027)",
            "Mi": "Geschlossen (Sanierung bis Frühjahr 2027)",
            "Do": "Geschlossen (Sanierung bis Frühjahr 2027)",
            "Fr": "Geschlossen (Sanierung bis Frühjahr 2027)",
            "Sa": "Geschlossen (Sanierung bis Frühjahr 2027)",
            "So": "Geschlossen (Sanierung bis Frühjahr 2027)",
        },
    },
    {
        "name": "Stadionbad",
        "adresse": "Robert-Enke-Straße 5, 30169 Hannover",
        "zeiten": {
            "Mo": "14:00-22:30",
            "Di": "06:30-16:00",
            "Mi": "06:30-22:30",
            "Do": "06:30-16:00",
            "Fr": "06:30-16:00",
            "Sa": "geschlossen",
            "So": "09:00-18:00",
        },
    },
    {
        "name": "Stöckener Bad",
        "adresse": "Hogrefestraße 45, 30419 Hannover",
        "zeiten": {
            "Mo": "06:30-09:30",
            "Di": "06:30-09:30",
            "Mi": "06:30-09:30; 10:00-12:30 (Frauen); 13:00-21:30",
            "Do": "06:30-09:30",
            "Fr": "06:30-09:30",
            "Sa": "08:00-17:00 (ab 14:00 Kinderspielnachmittag)",
            "So": "08:00-13:30",
        },
    },
    {
        "name": "Vahrenwalder Bad",
        "adresse": "Vahrenwalder Straße 100, 30165 Hannover",
        "zeiten": {
            "Mo": "06:00-18:00",
            "Di": "06:00-21:30",
            "Mi": "12:00-17:00",
            "Do": "06:00-21:30",
            "Fr": "06:00-17:00 (Frauen 17:30-20:30)",
            "Sa": "08:00-21:30",
            "So": "09:00-18:00",
        },
    },
]

FREIBAEDER = [
    {
        "name": "Kleefelder Bad (Annabad)",
        "adresse": "Haubergstraße 17, 30625 Hannover",
        "zeiten": {
            "Mo": "06:00-20:00",
            "Di": "06:00-20:00",
            "Mi": "06:00-20:00",
            "Do": "06:00-20:00",
            "Fr": "06:00-20:00",
            "Sa": "08:00-20:00",
            "So": "08:00-20:00",
        },
    },
    {
        "name": "Lister Bad",
        "adresse": "Am Lister Bad 1, 30179 Hannover",
        "zeiten": {
            "Mo": "06:00-20:30",
            "Di": "06:00-20:30",
            "Mi": "06:00-20:30",
            "Do": "06:00-20:30",
            "Fr": "06:00-20:30",
            "Sa": "08:00-20:30",
            "So": "08:00-20:30",
        },
    },
    {
        "name": "Misburger Freibad (Kombibad)",
        "adresse": "Seckbruchstraße 18, 30629 Hannover",
        "zeiten": {
            "Mo": "06:30-20:00",
            "Di": "06:30-20:00",
            "Mi": "06:30-20:00",
            "Do": "06:30-20:00",
            "Fr": "06:30-20:00",
            "Sa": "08:00-20:00",
            "So": "08:00-20:00",
        },
    },
    {
        "name": "Ricklinger Bad",
        "adresse": "Kneippweg 25, 30459 Hannover",
        "zeiten": {
            "Mo": "06:00-20:00",
            "Di": "06:00-20:00",
            "Mi": "06:00-20:00",
            "Do": "06:00-20:00",
            "Fr": "06:00-20:00",
            "Sa": "08:00-20:00",
            "So": "08:00-20:00",
        },
    },
    {
        "name": "RSV-Bad Leinhausen",
        "adresse": "Elbestraße 39, 30419 Hannover",
        "zeiten": {
            "Mo": "08:00-19:30",
            "Di": "08:00-19:30",
            "Mi": "08:00-19:30",
            "Do": "08:00-19:30",
            "Fr": "08:00-19:30",
            "Sa": "08:00-19:30",
            "So": "08:00-19:30",
        },
    },
    {
        "name": "Volksbad Limmer",
        "adresse": "Stockhardtweg 6, 30453 Hannover",
        "zeiten": {
            "Mo": "09:30-20:00",
            "Di": "09:30-20:00",
            "Mi": "09:30-20:00",
            "Do": "09:30-20:00",
            "Fr": "09:30-20:00",
            "Sa": "09:30-20:00",
            "So": "09:30-20:00",
        },
    },
]

BESONDERE_BAEDER = [
    {
        "name": "Freibad Bokeloh",
        "adresse": "Steinhuder Straße 49, 31515 Wunstorf",
        "zeiten": {
            "Mo": "10:00-19:00",
            "Di": "10:00-19:00",
            "Mi": "10:00-19:00",
            "Do": "10:00-19:00",
            "Fr": "10:00-19:00",
            "Sa": "10:00-19:00",
            "So": "10:00-19:00",
        },
        "hinweis": "Temperatur je nach Witterung 24-28°C",
    },
    {
        "name": "Hainhölzer Naturbad",
        "adresse": "Voltmerstraße 56, 30165 Hannover",
        "zeiten": {
            "Mo": "14:00-19:00",
            "Di": "14:00-19:00",
            "Mi": "14:00-19:00",
            "Do": "14:00-19:00",
            "Fr": "14:00-19:00",
            "Sa": "14:00-19:00",
            "So": "14:00-19:00",
        },
        "hinweis": "Ohne Chlor",
    },
]

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def ist_freibad_saison(datum: date = None) -> bool:
    if datum is None:
        datum = date.today()
    return FREIBAD_SAISON_START <= datum <= FREIBAD_SAISON_ENDE


def get_offene_baeder(wochentag: str, datum: date = None) -> str:
    """Gibt eine formatierte Übersicht aller offenen Bäder für einen Wochentag zurück."""
    if wochentag not in WOCHENTAGE:
        return "Ungültiger Wochentag. Nutze: Mo, Di, Mi, Do, Fr, Sa, So"

    result = []

    # Hallenbäder (ganzjährig)
    result.append("🏊 **Hallenbäder:**")
    for bad in HALLENBAEDER:
        zeit = bad["zeiten"][wochentag]
        if "geschlossen" in zeit.lower() or "sanierung" in zeit.lower():
            continue
        result.append(f"  • {bad['name']}: {zeit}")
        result.append(f"    📍 {bad['adresse']}")

    # Freibäder (nur in Saison)
    if ist_freibad_saison(datum):
        result.append("\n🏖️ **Freibäder (Saison 14.05. - 13.09.2026):**")
        for bad in FREIBAEDER:
            zeit = bad["zeiten"][wochentag]
            result.append(f"  • {bad['name']}: {zeit}")
            result.append(f"    📍 {bad['adresse']}")

        result.append("\n🌿 **Besondere Bäder:**")
        for bad in BESONDERE_BAEDER:
            zeit = bad["zeiten"][wochentag]
            result.append(f"  • {bad['name']}: {zeit}")
            result.append(f"    📍 {bad['adresse']}")
            if bad.get("hinweis"):
                result.append(f"    ℹ️ {bad['hinweis']}")
    else:
        result.append("\n🏖️ Freibäder: Außerhalb der Saison (14.05. - 13.09.2026)")

    return "\n".join(result)


def get_schwimm_info_fuer_prompt(datum: date = None) -> str:
    """Gibt Schwimmbad-Infos zurück, die in den Coach-Prompt eingefügt werden können."""
    if datum is None:
        datum = date.today()

    saison = "JA ✅" if ist_freibad_saison(datum) else "NEIN ❌"

    info = f"Freibad-Saison aktiv: {saison}\n\n"
    for tag in WOCHENTAGE:
        info += f"**{tag}:**\n{get_offene_baeder(tag, datum)}\n\n"
    return info
