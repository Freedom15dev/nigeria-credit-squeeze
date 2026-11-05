"""House chart style for the series: white background, navy text, blue main series,
orange highlights, light grey gridlines on y only, and a source line on every chart."""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

NAVY = "#0F1E33"
BLUE = "#2A6FDB"
ORANGE = "#D9822B"
GREY = "#8A94A6"
LIGHT_GREY = "#E3E6EB"
PALE_BLUE = "#CFE0F8"
PALE_ORANGE = "#F6DCC2"

SOURCE = "Source: CBN · Analysis: Freedom Oboh"
CHARTS_DIR = Path(__file__).resolve().parents[1] / "charts"


def apply():
    mpl.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "text.color": NAVY,
        "axes.labelcolor": NAVY,
        "axes.edgecolor": GREY,
        "xtick.color": NAVY,
        "ytick.color": NAVY,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": LIGHT_GREY,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 11,
        "axes.titlesize": 15,
        "legend.frameon": False,
        "figure.dpi": 110,
    })


def titles(fig, ax, title, subtitle):
    """Finding as the title, measure as the subtitle, both left-aligned at the top."""
    fig._house_titles = (title, subtitle)


def finish(fig, filename, source=SOURCE, top=0.88):
    """Lay out the figure, add titles and the source line, and save to charts/."""
    fig.tight_layout(rect=(0, 0.035, 1, top))
    title, subtitle = getattr(fig, "_house_titles", ("", ""))
    fig.text(0.01, 0.985, title, fontsize=15, fontweight="bold", color=NAVY, ha="left", va="top")
    fig.text(0.01, 0.935, subtitle, fontsize=11, color=GREY, ha="left", va="top")
    fig.text(0.01, 0.005, source, fontsize=9, color=GREY, ha="left", va="bottom")
    CHARTS_DIR.mkdir(exist_ok=True)
    path = CHARTS_DIR / filename
    fig.savefig(path, dpi=160, bbox_inches="tight")
    return path
