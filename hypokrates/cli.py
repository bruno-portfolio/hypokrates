"""CLI para hypokrates — farmacovigilancia computacional."""

from __future__ import annotations

import typer

from hypokrates.constants import __version__

app = typer.Typer(
    name="hypokrates",
    help="Pharmacovigilance signal detection and hypothesis generation.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"hypokrates {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Pharmacovigilance signal detection and hypothesis generation."""


@app.command()
def scan(
    drugs: list[str] = typer.Argument(..., help="Drug name(s) to scan"),
    top_n: int = typer.Option(10, "--top-n", "-n", help="Top events to scan"),
    check_labels: bool = typer.Option(False, "--labels", help="Check FDA labels"),
    check_trials: bool = typer.Option(False, "--trials", help="Check clinical trials"),
    check_chembl: bool = typer.Option(False, "--chembl", help="Check ChEMBL mechanism"),
    check_opentargets: bool = typer.Option(False, "--opentargets", help="Check OpenTargets"),
    suspect_only: bool = typer.Option(False, "--suspect-only", help="Suspect reports only"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output: table|json"),
) -> None:
    """Scan adverse events for one or more drugs."""
    from hypokrates.sync import scan as scan_mod

    for drug in drugs:
        typer.echo(f"\n{'=' * 60}")
        typer.echo(f"Scanning: {drug.upper()}")
        typer.echo(f"{'=' * 60}\n")

        result = scan_mod.scan_drug(
            drug,
            top_n=top_n,
            check_labels=check_labels,
            check_trials=check_trials,
            check_chembl=check_chembl,
            check_opentargets=check_opentargets,
            suspect_only=suspect_only,
        )

        if output_format == "json":
            typer.echo(result.model_dump_json(indent=2))
        else:
            _print_scan(result)


@app.command()
def signal(
    drug: str = typer.Argument(..., help="Drug name"),
    event: str = typer.Argument(..., help="Adverse event term"),
    suspect_only: bool = typer.Option(False, "--suspect-only"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output: table|json"),
) -> None:
    """Detect disproportionality signal for a drug-event pair."""
    from hypokrates.sync import stats

    result = stats.signal(drug, event, suspect_only=suspect_only)

    if output_format == "json":
        typer.echo(result.model_dump_json(indent=2))
    else:
        _print_signal(result)


@app.command()
def compare(
    drug: str = typer.Argument(..., help="Primary drug"),
    control: str = typer.Argument(..., help="Control drug (same class)"),
    events: str | None = typer.Option(None, "--events", "-e", help="Comma-separated events"),
    top_n: int = typer.Option(10, "--top-n", "-n"),
    suspect_only: bool = typer.Option(False, "--suspect-only"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output: table|json"),
) -> None:
    """Compare signals between two drugs (intra-class)."""
    from hypokrates.sync import cross

    event_list: list[str] | None = None
    if events:
        event_list = [e.strip() for e in events.split(",")]

    result = cross.compare_signals(
        drug, control, events=event_list, top_n=top_n, suspect_only=suspect_only
    )

    if output_format == "json":
        typer.echo(result.model_dump_json(indent=2))
    else:
        _print_compare(result)


@app.command()
def timeline(
    drug: str = typer.Argument(..., help="Drug name"),
    event: str = typer.Argument(..., help="Adverse event term"),
    suspect_only: bool = typer.Option(False, "--suspect-only"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output: table|json"),
) -> None:
    """Build quarterly time series of FAERS reports for a drug-event pair."""
    from hypokrates.sync import stats

    result = stats.signal_timeline(drug, event, suspect_only=suspect_only)

    if output_format == "json":
        typer.echo(result.model_dump_json(indent=2))
    else:
        _print_timeline(result)


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _print_scan(result: object) -> None:
    """Formata scan result para terminal."""
    drug = getattr(result, "drug", "")
    items = getattr(result, "items", [])
    novel = getattr(result, "novel_count", 0)
    emerging = getattr(result, "emerging_count", 0)
    known = getattr(result, "known_count", 0)
    mechanism = getattr(result, "mechanism", None)
    filtered = getattr(result, "filtered_operational_count", 0)

    typer.echo(f"Drug: {drug.upper()}")
    typer.echo(f"Results: {novel} novel, {emerging} emerging, {known} known")
    if filtered > 0:
        typer.echo(f"Filtered: {filtered} operational terms")
    if mechanism:
        typer.echo(f"Mechanism: {mechanism[:200]}")
    typer.echo("")

    if not items:
        typer.echo("No events found.")
        return

    typer.echo(f"{'#':>3} {'Event':<35} {'Class':<18} {'PRR':>8} {'Lit':>5} {'Label':>6}")
    typer.echo("-" * 80)

    for item in items:
        rank = getattr(item, "rank", 0)
        event = getattr(item, "event", "")[:34]
        cls = getattr(item, "classification", "")
        cls_val = cls.value if hasattr(cls, "value") else str(cls)
        sig = getattr(item, "signal", None)
        prr = f"{sig.prr.value:.1f}" if sig else "?"
        lit = getattr(item, "literature_count", 0)
        in_label = getattr(item, "in_label", None)
        label_str = "YES" if in_label is True else ("NO" if in_label is False else "-")
        vol = " !" if getattr(item, "volume_flag", False) else ""

        typer.echo(f"{rank:>3} {event:<35} {cls_val:<18} {prr:>8} {lit:>5} {label_str:>6}{vol}")

    typer.echo("")
    typer.echo("Note: PRR = disproportionality of reporting, not absolute risk.")


def _print_signal(result: object) -> None:
    """Formata signal result para terminal."""
    drug = getattr(result, "drug", "")
    event = getattr(result, "event", "")
    detected = getattr(result, "signal_detected", False)
    table = getattr(result, "table", None)
    prr = getattr(result, "prr", None)
    ror = getattr(result, "ror", None)
    ic = getattr(result, "ic", None)

    typer.echo(f"{drug.upper()} + {event.upper()}")
    typer.echo(f"Signal: {'YES' if detected else 'NO'}")
    typer.echo("")

    ebgm = getattr(result, "ebgm", None)

    for name, m in [("PRR", prr), ("ROR", ror), ("IC", ic), ("EBGM", ebgm)]:
        if m is None:
            continue
        sig = "*" if getattr(m, "significant", False) else ""
        typer.echo(f"  {name}: {m.value:.2f} (95% CI: {m.ci_lower:.2f}-{m.ci_upper:.2f}) {sig}")

    if table:
        typer.echo("")
        typer.echo(f"  a (drug+event):    {table.a:>10}")
        typer.echo(f"  b (drug+!event):   {table.b:>10}")
        typer.echo(f"  c (!drug+event):   {table.c:>10}")
        typer.echo(f"  d (!drug+!event):  {table.d:>10}")


def _print_compare(result: object) -> None:
    """Formata compare result para terminal."""
    drug = getattr(result, "drug", "")
    control = getattr(result, "control", "")
    items = getattr(result, "items", [])
    drug_unique = getattr(result, "drug_unique_signals", 0)
    ctrl_unique = getattr(result, "control_unique_signals", 0)

    typer.echo(f"{drug.upper()} vs {control.upper()}")
    typer.echo(
        f"Drug-only signals: {drug_unique} | "
        f"Control-only: {ctrl_unique} | "
        f"Both: {getattr(result, 'both_detected', 0)}"
    )
    typer.echo("")

    if not items:
        typer.echo("No events to compare.")
        return

    typer.echo(f"{'Event':<30} {'Drug PRR':>10} {'Ctrl PRR':>10} {'Ratio':>8} {'Stronger':>10}")
    typer.echo("-" * 72)

    for item in items:
        event = getattr(item, "event", "")[:29]
        d_prr = getattr(item, "drug_prr", 0.0)
        c_prr = getattr(item, "control_prr", 0.0)
        ratio = getattr(item, "ratio", 0.0)
        stronger = getattr(item, "stronger", "")
        ratio_str = f"{ratio:.1f}x" if ratio != float("inf") else "inf"
        typer.echo(f"{event:<30} {d_prr:>10.2f} {c_prr:>10.2f} {ratio_str:>8} {stronger:>10}")


def _print_timeline(result: object) -> None:
    """Formata timeline result para terminal."""
    drug = getattr(result, "drug", "")
    event = getattr(result, "event", "")
    quarters = getattr(result, "quarters", [])
    total = getattr(result, "total_reports", 0)
    mean = getattr(result, "mean_quarterly", 0.0)
    std = getattr(result, "std_quarterly", 0.0)
    spikes = getattr(result, "spike_quarters", [])
    peak = getattr(result, "peak_quarter", None)

    typer.echo(f"{drug.upper()} + {event.upper()}")
    typer.echo(f"Total: {total} reports across {len(quarters)} quarters")
    typer.echo(f"Mean/quarter: {mean:.1f} (std: {std:.1f})")
    if peak:
        typer.echo(f"Peak: {peak.label} ({peak.count} reports)")
    if spikes:
        spike_labels = [f"{s.label} ({s.count})" for s in spikes]
        typer.echo(f"Spikes: {', '.join(spike_labels)}")
    typer.echo("")

    spike_set = {(s.year, s.quarter) for s in spikes}
    for q in quarters:
        marker = " *** SPIKE" if (q.year, q.quarter) in spike_set else ""
        bar_len = min(q.count * 50 // max(total, 1), 50)
        bar = "#" * bar_len
        typer.echo(f"  {q.label}: {q.count:>6} {bar}{marker}")
