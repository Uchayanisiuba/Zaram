"""Charts: building the image, and getting it back out of the HTML.

Two jobs that look like one, and are split because their dependencies differ.

`build_png` turns data into an image, and needs matplotlib. `ChartExporter`
pulls the image back out of the artifact's HTML, and needs nothing — the PNG is
embedded there as a data URI, so exporting a chart is a base64 decode. That
asymmetry is why the exporter reports itself available on a machine with no
matplotlib: an artifact that already exists can always be saved out, and
refusing to hand a user a file that is already sitting in the record would be a
dependency check reported as a capability.

Colour
------
Eight categorical slots, assigned by series index in fixed order, never cycled.
The order is the colourblind-safety mechanism rather than a preference: adjacent
pairs are the ones a reader compares, and this ordering was validated against the
white surface these charts are printed on — worst adjacent pair ΔE 9.1 under
protanopia, 19.6 unsimulated. Three of the slots fall below 3:1 contrast against
white, which obligates *relief*: visible labels or a readable table. That is why
`html.render_chart` always emits the data table under the image and why nothing
here offers a way to turn it off. The picture is never the only copy of the
numbers.

A ninth series is refused rather than given an invented hue. A generated colour
is one a reader cannot distinguish and a caller cannot predict; facet the data or
fold the tail into a total instead.

Deliberately not offered
------------------------
**Pie charts**, because judging angle is worse than judging length for every
question a business asks of its own numbers, and "which of these is biggest" is
most of them. **Two y-axes**, because the reader cannot tell which curve belongs
to which scale, and the apparent crossing point is an artifact of two arbitrary
ranges. Two measures of different scale are two charts.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Sequence

from .base import AVAILABLE, Availability, module_available

#: Categorical slots, in fixed order. Light-surface steps: these are printed on
#: white paper and embedded in documents, so there is no dark variant — the
#: chart deliberately commits to one look rather than tracking a theme it will
#: not be viewed in.
PALETTE = (
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
)

_INK = "#0b0b0b"
_INK_SECONDARY = "#52514e"
_MUTED = "#898781"
_GRID = "#e1e0d9"
_BASELINE = "#c3c2b7"
_SURFACE = "#ffffff"

#: Past this, a bar chart's value labels collide and stop being relief.
_MAX_DIRECT_LABELS = 12

_DATA_URI = re.compile(
    r'src="data:image/png;base64,([A-Za-z0-9+/=\s]+)"', re.IGNORECASE
)


class TooManySeries(ValueError):
    """More series than there are distinguishable colours."""


@dataclass(frozen=True)
class Series:
    """One line, or one group of bars."""

    label: str
    values: Sequence[float]


@dataclass(frozen=True)
class ChartSpec:
    """What to draw. Deliberately small — every field here is one a caller can
    answer from the user's own data, and nothing is a styling knob."""

    title: str
    #: "bar" for magnitude across categories, "hbar" when the labels are long or
    #: numerous, "line" for change over time. The form follows the question.
    kind: str
    categories: Sequence[str]
    series: Sequence[Series] = field(default_factory=list)
    y_label: str = ""
    #: A format string applied to direct labels, e.g. "₦{:,.0f}". The axis keeps
    #: plain numbers; a currency symbol on every tick is noise.
    value_format: str = "{:,.0f}"


def build_availability() -> Availability:
    """Whether a *new* chart can be drawn here. Distinct from exporting one."""
    return module_available("matplotlib", needed_for="Chart generation")


def build_png(spec: ChartSpec, *, width_in: float = 7.5, height_in: float = 4.2) -> bytes:
    """Draw the chart. Returns PNG bytes; touches no file and no global state.

    The object-oriented API rather than pyplot, deliberately: pyplot keeps a
    global figure registry, and in a long-lived backend process that is a leak
    and a source of one request's axes appearing in another's image.
    """
    availability = build_availability()
    if not availability.ok:
        from .base import ExportUnavailable

        raise ExportUnavailable("chart", availability)

    import matplotlib

    # Before any backend-selecting import. Agg is headless; the default backend
    # on a desktop tries to reach a display server that a backend process does
    # not have.
    matplotlib.use("Agg", force=False)
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    if len(spec.series) > len(PALETTE):
        raise TooManySeries(
            f"{len(spec.series)} series but {len(PALETTE)} distinguishable colours. "
            "Facet the chart or fold the tail into a total — a generated ninth "
            "hue is one the reader cannot tell from the others."
        )
    if not spec.series:
        raise ValueError("a chart with no series has nothing to draw")

    figure = Figure(figsize=(width_in, height_in), dpi=200, facecolor=_SURFACE)
    canvas = FigureCanvasAgg(figure)
    axes = figure.add_subplot(111)
    axes.set_facecolor(_SURFACE)

    _apply_font()

    if spec.kind == "line":
        _draw_line(axes, spec)
    elif spec.kind in ("bar", "hbar"):
        _draw_bars(axes, spec, horizontal=spec.kind == "hbar")
    else:
        raise ValueError(f"unknown chart kind {spec.kind!r}; use bar, hbar or line")

    _apply_chrome(axes, spec)

    # A legend identifies series; with one series the title already names it,
    # and a legend box saying the same word twice is furniture.
    if len(spec.series) > 1:
        legend = axes.legend(
            loc="upper left",
            bbox_to_anchor=(0, -0.12),
            ncol=min(len(spec.series), 4),
            frameon=False,
            fontsize=8,
        )
        for text in legend.get_texts():
            text.set_color(_INK_SECONDARY)

    figure.tight_layout()

    from io import BytesIO

    buffer = BytesIO()
    canvas.print_png(buffer)
    return buffer.getvalue()


def _apply_font() -> None:
    """System sans, with matplotlib's own bundled face as the floor.

    DejaVu Sans ships with matplotlib, so the list always resolves to something
    real. Without a guaranteed tail, a machine missing Segoe UI renders every
    label in whatever matplotlib falls back to, with a warning per glyph.
    """
    import matplotlib

    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = [
        "Segoe UI",
        "Helvetica Neue",
        "Arial",
        "DejaVu Sans",
    ]


def _draw_bars(axes, spec: ChartSpec, *, horizontal: bool) -> None:
    count = len(spec.series)
    positions = range(len(spec.categories))

    # A gap between adjacent bars, so two fills never touch. Touching fills read
    # as one wide bar of an ambiguous colour at small sizes.
    group_width = 0.8
    bar_width = group_width / count * 0.92

    for index, series in enumerate(spec.series):
        offset = (index - (count - 1) / 2) * (group_width / count)
        shifted = [position + offset for position in positions]
        colour = PALETTE[index]

        if horizontal:
            axes.barh(shifted, list(series.values), height=bar_width,
                      color=colour, label=series.label, zorder=3)
        else:
            axes.bar(shifted, list(series.values), width=bar_width,
                     color=colour, label=series.label, zorder=3)

    _label_bars(axes, spec, horizontal=horizontal)

    ticks = list(positions)
    if horizontal:
        axes.set_yticks(ticks)
        axes.set_yticklabels(list(spec.categories))
    else:
        axes.set_xticks(ticks)
        axes.set_xticklabels(list(spec.categories))


def _label_bars(axes, spec: ChartSpec, *, horizontal: bool) -> None:
    """Values on the bars — the relief that low-contrast slots require.

    Suppressed past `_MAX_DIRECT_LABELS`, where the labels overlap each other
    and stop being readable. The data table under every chart is the relief that
    always holds; this is the one that is nicer when it fits.
    """
    total_bars = len(spec.categories) * len(spec.series)
    if total_bars > _MAX_DIRECT_LABELS:
        return

    for container in axes.containers:
        axes.bar_label(
            container,
            fmt=lambda value: spec.value_format.format(value),
            padding=3,
            fontsize=8,
            color=_INK_SECONDARY,
        )


def _draw_line(axes, spec: ChartSpec) -> None:
    positions = list(range(len(spec.categories)))

    for index, series in enumerate(spec.series):
        colour = PALETTE[index]
        axes.plot(
            positions,
            list(series.values),
            color=colour,
            linewidth=2,
            marker="o",
            markersize=4.5,
            markeredgecolor=_SURFACE,
            markeredgewidth=1,
            label=series.label,
            zorder=3,
        )

        # The last point only. A number on every point is the anti-pattern —
        # it turns the line into a table that is harder to read than a table.
        if series.values:
            axes.annotate(
                spec.value_format.format(series.values[-1]),
                xy=(positions[-1], series.values[-1]),
                xytext=(6, 0),
                textcoords="offset points",
                fontsize=8,
                color=_INK_SECONDARY,
                va="center",
            )

    axes.set_xticks(positions)
    axes.set_xticklabels(list(spec.categories))


def _format_value_axis(axes, *, horizontal: bool) -> None:
    """Ticks a non-technical reader can read at a glance.

    Two fixes to matplotlib's defaults, both mandatory rather than cosmetic.

    **The offset notation goes.** By default a naira axis in the millions grows
    a `1e6` in the corner and labels its ticks `1.75`. A reader who misses the
    corner reads the chart as being about single naira, wrong by a factor of a
    million. That is not a styling preference — it is a chart that states the
    wrong number, in a product whose claim is that its output is defensible.

    **Round magnitudes get a suffix**: 1.8M, 850K. Rounding on an axis is safe
    here because it is never the only copy of the value — the bars carry exact
    direct labels and `render_chart` always emits the data table underneath.
    """
    from matplotlib.ticker import FuncFormatter

    axis = axes.xaxis if horizontal else axes.yaxis
    axis.get_major_formatter().set_useOffset(False)
    axis.set_major_formatter(FuncFormatter(lambda value, _: _compact(value)))


def _compact(value: float) -> str:
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"{value / 1_000_000:,.1f}".rstrip("0").rstrip(".") + "M"
    if magnitude >= 1_000:
        return f"{value / 1_000:,.0f}K"
    return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"


def _apply_chrome(axes, spec: ChartSpec) -> None:
    """Recessive everything. The data is the only thing meant to be seen."""
    axes.set_title(
        spec.title, color=_INK, fontsize=12, loc="left", pad=12, fontweight="600"
    )
    if spec.y_label:
        axes.set_ylabel(spec.y_label, color=_INK_SECONDARY, fontsize=9)

    horizontal = spec.kind == "hbar"
    axes.grid(
        axis="x" if horizontal else "y",
        color=_GRID,
        linewidth=0.8,
        zorder=0,
    )
    axes.set_axisbelow(True)
    _format_value_axis(axes, horizontal=horizontal)

    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(_BASELINE)
        axes.spines[side].set_linewidth(0.8)

    axes.tick_params(colors=_MUTED, labelsize=8, length=0)
    for label in axes.get_xticklabels() + axes.get_yticklabels():
        label.set_color(_MUTED)


class ChartExporter:
    """The image, taken back out of the HTML that holds it."""

    extension = "png"
    media_type = "image/png"
    label = "Chart image"

    def availability(self) -> Availability:
        # Always. Extraction is a base64 decode; matplotlib is needed to *make*
        # a chart, which already happened by the time an artifact exists.
        return AVAILABLE

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        match = _DATA_URI.search(document_html)
        if not match:
            raise ValueError(
                "no embedded PNG in this artifact's HTML — export as png is only "
                "meaningful for a chart, and this artifact does not contain one"
            )

        return base64.b64decode(re.sub(r"\s+", "", match.group(1)))
