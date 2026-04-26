"""
Generiert Trainingsfortschritt-Grafiken als PNG für Telegram.
"""
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_progress_chart(logs: list[dict]) -> io.BytesIO | None:
    """Erstellt eine TSS/CTL/ATL-Grafik aus Training-Logs. Gibt PNG als BytesIO zurück."""
    if not logs or len(logs) < 2:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        logger.warning("matplotlib nicht installiert — keine Grafiken verfügbar")
        return None

    from estimator import parse_metrics_from_text

    dates = []
    tss_values = []
    ctl_values = []
    atl_values = []
    tsb_values = []

    for log in reversed(logs):  # Älteste zuerst
        metrics = parse_metrics_from_text(log.get("data_json", ""))
        if not metrics.get("tss") and not metrics.get("ctl"):
            continue

        try:
            created = log.get("created_at", "")
            dt = datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            continue

        dates.append(dt)
        tss_values.append(metrics.get("tss", 0))
        ctl_values.append(metrics.get("ctl", 0))
        atl_values.append(metrics.get("atl", 0))
        tsb_values.append(metrics.get("tsb", 0))

    if len(dates) < 2:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    fig.suptitle("📊 Trainingsfortschritt", fontsize=14, fontweight="bold")

    # Oberer Chart: CTL, ATL, TSS
    ax1.plot(dates, ctl_values, "b-o", label="CTL (Fitness)", markersize=4)
    ax1.plot(dates, atl_values, "r-o", label="ATL (Ermüdung)", markersize=4)
    ax1.bar(dates, tss_values, width=2, alpha=0.3, color="gray", label="TSS")
    ax1.set_ylabel("Wert")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Unterer Chart: TSB (Form)
    colors = ["green" if v >= 0 else "red" for v in tsb_values]
    ax2.bar(dates, tsb_values, width=2, color=colors, alpha=0.7)
    ax2.axhline(y=0, color="black", linewidth=0.5)
    ax2.axhline(y=-30, color="red", linewidth=0.5, linestyle="--", label="Deload-Grenze")
    ax2.set_ylabel("TSB (Form)")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.3)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
