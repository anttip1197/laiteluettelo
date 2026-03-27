"""
Laiteluettelo - Pääohjelma

Käyttö:
  python main.py TK01.pdf                   # Perusajo
  python main.py TK01.pdf --tarkista        # Tarkista ennen tallennusta
  python main.py TK01.pdf --tallenna-esimerkki  # Kerää training-dataa
  python main.py status                     # Tarkista Ollama + dataset
"""
import sys
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich import box

console = Console()


# ── Apufunktiot ───────────────────────────────────────────────────────────────

def _format_data(data: dict) -> str:
    """Muotoile data-dict luettavaksi merkkijonoksi."""
    if not data:
        return "[dim]—[/dim]"
    labels = {
        "ilma_dp": "ΔP ilma", "ilma_dp_mitoitus": "ΔP mitoitus",
        "ilma_dp_alku": "ΔP alku", "ilma_dp_loppu": "ΔP loppu",
        "suodatinluokka": "Luokka", "ilma_lampotila_ennen": "T ennen",
        "ilma_lampotila_jalkeen": "T jälkeen", "nestevirta": "Nestevirta",
        "neste_dp": "ΔP neste", "neste_meno": "T meno", "neste_paluu": "T paluu",
        "ilmamaara": "Ilmavirta", "mitoituspaine": "Paine",
        "sahkoteho": "Teho", "jannite_virta": "Jännite",
        "hyotysuhde_en308": "Hyöts. EN308",
    }
    unit_map = {
        "ilma_dp": "Pa", "ilma_dp_mitoitus": "Pa", "ilma_dp_alku": "Pa",
        "ilma_dp_loppu": "Pa", "ilma_lampotila_ennen": "°C",
        "ilma_lampotila_jalkeen": "°C", "nestevirta": "l/s",
        "neste_dp": "kPa", "neste_meno": "°C", "neste_paluu": "°C",
        "ilmamaara": "m³/s", "mitoituspaine": "Pa",
        "sahkoteho": "kW", "hyotysuhde_en308": "%",
    }
    parts = []
    for key, val in data.items():
        if val is None:
            continue
        label = labels.get(key, key)
        u = unit_map.get(key, "")
        parts.append(f"{label}: {val}{' ' + u if u else ''}")
    return "  |  ".join(parts)


def _print_extracted_unit(unit) -> None:
    """Tulosta puretut tiedot konsoliin taulukkona."""
    table = Table(
        title=f"Puretut laitteet — {unit.unit_code}",
        box=box.ROUNDED, show_lines=True,
    )
    table.add_column("Tunnus", style="bold cyan", width=8)
    table.add_column("Laite", width=24)
    table.add_column("Puoli", width=8)
    table.add_column("Tiedot", width=65)

    for comp in unit.components:
        for row_idx, comp_row in enumerate(comp.rows):
            label = comp.name
            if comp_row.row_label:
                label = f"{comp.name} / {comp_row.row_label}"
            side_fi = {"supply": "Tulo", "exhaust": "Poisto", "both": "—"}.get(comp.side, comp.side)
            if comp.type_prefix == "LTO":
                side_fi = "Tulo" if row_idx == 0 else "Poisto"
            table.add_row(
                comp.code if row_idx == 0 else "",
                label, side_fi,
                _format_data(comp_row.data),
            )

    console.print(table)


def _interactive_review(unit) -> bool:
    """
    Interaktiivinen tarkistus: näytä puretut tiedot ja kysy hyväksyntä.
    Palauttaa True jos käyttäjä hyväksyy, False jos hylkää.
    """
    _print_extracted_unit(unit)
    console.print()
    ok = Confirm.ask("[bold]Näyttääkö data oikealta?[/bold]")
    return ok


def run_extraction(
    pdf_path: str,
    model: str | None = None,
    use_finetuned: bool = False,
    output: str | None = None,
    tallenna_esimerkki: bool = False,
    tarkista: bool = False,
    auto_open: bool = True,
) -> None:
    """Suorita täydellinen purku + Excel-generointi."""
    from src.pdf_extractor import extract_text_from_pdf, get_pdf_metadata
    from src.llm_extractor import (
        extract_from_pdf_text, check_ollama_running,
        list_available_models, select_best_model,
    )
    from src.excel_generator import generate_excel
    from src.dataset_builder import save_example as save_ex, get_dataset_stats

    pdf_path = Path(pdf_path)

    console.print(Panel(
        f"[bold]LVI Laiteluettelo[/bold]\n"
        f"Koneajokortti: [cyan]{pdf_path.name}[/cyan]",
        expand=False,
    ))

    # 1. Tarkista malli
    if use_finetuned:
        console.print("  [cyan]Malli: fine-tuned (paikallinen)[/cyan]")
    else:
        # Tarkista Ollama
        if not check_ollama_running():
            console.print(Panel(
            "[red bold]Ollama ei ole käynnissä![/red bold]\n\n"
            "  1. Asenna:    [link=https://ollama.com]https://ollama.com[/link]\n"
            "  2. Lataa malli: [yellow]ollama pull mistral[/yellow]\n"
            "  3. Käynnistä:  [yellow]ollama serve[/yellow]",
            title="Virhe", border_style="red",
        ))
        sys.exit(1)

    if not use_finetuned:
        available = list_available_models()
        if not available:
            console.print("[red]Ei malleja![/red] Lataa: [yellow]ollama pull mistral[/yellow]")
            sys.exit(1)

        chosen_model = model or select_best_model()
        console.print(f"  Malli: [bold]{chosen_model}[/bold]  "
                      f"Saatavilla: {', '.join(available)}")
    else:
        # Check fine-tuned model exists
        finetuned_path = Path(__file__).parent / "training" / "model_output" / "laiteluettelo_merged"
        if not finetuned_path.exists():
            console.print(f"[red]Fine-tuned malli ei löydy: {finetuned_path}[/red]")
            sys.exit(1)
        chosen_model = "finetuned"

    # 2. Lue PDF
    console.print("\n[dim]Luetaan PDF...[/dim]")
    try:
        meta = get_pdf_metadata(pdf_path)
        pdf_text = extract_text_from_pdf(pdf_path)
    except FileNotFoundError:
        console.print(f"[red]PDF ei löydy: {pdf_path}[/red]")
        sys.exit(1)

    unit_code = meta.get("unit_code") or "TK??"
    console.print(
        f"  Kone: [bold]{unit_code}[/bold]  "
        f"Valmistaja: [bold]{meta.get('manufacturer') or '?'}[/bold]  "
        f"Projekti: [bold]{meta.get('project') or '?'}[/bold]"
    )

    # 3. LLM-purku
    try:
        if use_finetuned:
            from src.inference_finetuned import extract_with_finetuned
            from src.llm_extractor import build_extracted_unit

            console.print("[cyan]Käytetään fine-tuned-mallia (ei Ollama)[/cyan]")
            raw_json = extract_with_finetuned(pdf_text)
            if not raw_json:
                raise ValueError("Fine-tuned malli ei palauttanut kelvollista JSON:ia")
            unit = build_extracted_unit(raw_json, source_pdf=str(pdf_path))
        else:
            unit = extract_from_pdf_text(
                pdf_text,
                unit_code=unit_code,
                model=chosen_model,
                source_pdf=str(pdf_path),
            )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Purku epäonnistui:[/red] {e}")
        sys.exit(1)

    # 4. Näytä tulokset + mahdollinen tarkistus
    if tarkista:
        ok = _interactive_review(unit)
        if not ok:
            console.print("[yellow]Hylätty. Excel:iä ei tallennettu.[/yellow]")
            if tallenna_esimerkki:
                console.print("[dim]Training-esimerkkiä ei tallennettu (ei hyväksytty).[/dim]")
            return
    else:
        _print_extracted_unit(unit)

    # 5. Tallenna Excel
    if output:
        out_path = Path(output)
        if out_path.is_dir():
            out_path = out_path / f"laiteluettelo_{unit.unit_code}.xlsx"
    else:
        out_path = None

    excel_path = generate_excel(unit, output_path=out_path)
    console.print(f"\n[green bold]Excel tallennettu:[/green bold] [cyan]{excel_path}[/cyan]")

    # 6. Training-esimerkki
    if tallenna_esimerkki:
        verified = tarkista  # Jos käyttäjä hyväksyi tarkistuksessa → verified=True
        ex_path = save_ex(pdf_text, unit, verified=verified)
        stats = get_dataset_stats()
        console.print(
            f"[dim]Esimerkki tallennettu: {ex_path.name}  "
            f"(Dataset: {stats['total']} kpl, tarkistettu: {stats['verified']})[/dim]"
        )

    # 7. Avaa Excel
    if auto_open:
        import os
        try:
            os.startfile(excel_path)
        except Exception:
            pass  # Ei kriittinen virhe


# ── Click-komennot ────────────────────────────────────────────────────────────

@click.group()
def cli():
    """LVI-laiteluettelo automaattitäyttö paikallisella kielimallilla."""
    pass


@cli.command("purku")
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--model", "-m", default=None, help="Ollama-malli (esim. mistral, phi3.5)")
@click.option("--use-finetuned", is_flag=True, help="Käytä fine-tuned-mallia (ei Ollama)")
@click.option("--output", "-o", default=None, help="Tallennushakemisto tai .xlsx-polku")
@click.option("--tarkista", is_flag=True, help="Tarkista tulokset ennen tallennusta")
@click.option("--tallenna-esimerkki", is_flag=True, help="Tallenna training-esimerkiksi")
@click.option("--ei-avaa", is_flag=True, help="Älä avaa Exceliä automaattisesti")
def cmd_purku(pdf_path, model, use_finetuned, output, tarkista, tallenna_esimerkki, ei_avaa):
    """
    Pura koneajokortti ja generoi laiteluettelo-Excel.

    \b
    Esimerkit:
      python main.py purku TK01.pdf
      python main.py purku TK01.pdf --tarkista --tallenna-esimerkki
      python main.py purku TK01.pdf --model phi3.5 --output C:/Projektit/
    """
    run_extraction(
        pdf_path,
        model=model,
        use_finetuned=use_finetuned,
        output=output,
        tallenna_esimerkki=tallenna_esimerkki,
        tarkista=tarkista,
        auto_open=not ei_avaa,
    )


@cli.command("status")
def cmd_status():
    """Näytä Ollaman tila, mallit ja datasetin koko."""
    from src.llm_extractor import check_ollama_running, list_available_models, select_best_model
    from src.dataset_builder import get_dataset_stats

    console.print()
    if check_ollama_running():
        console.print("[green]● Ollama: käynnissä[/green]")
        models = list_available_models()
        if models:
            best = select_best_model()
            for m in models:
                marker = "[green]★[/green]" if m == best else " "
                console.print(f"  {marker} {m}")
        else:
            console.print("  [yellow]Ei malleja — lataa: ollama pull mistral[/yellow]")
    else:
        console.print("[red]● Ollama: ei käynnissä[/red]")
        console.print("  Käynnistä: [yellow]ollama serve[/yellow]")

    stats = get_dataset_stats()
    console.print(
        f"\n[bold]Training dataset:[/bold] {stats['total']} esimerkkiä "
        f"([green]{stats['verified']} tarkistettu[/green] / "
        f"[yellow]{stats['unverified']} tarkistamaton[/yellow])"
    )
    if stats["manufacturers"]:
        rows = "  ".join(f"{k}: {v}" for k, v in stats["manufacturers"].items())
        console.print(f"Valmistajat: {rows}")


@cli.command("dataset")
@click.option("--vie", is_flag=True, help="Vie JSONL-tiedostoon fine-tuningia varten")
@click.option("--kaikki", is_flag=True, help="Vie myös tarkistamattomat esimerkit")
def cmd_dataset(vie, kaikki):
    """Näytä ja hallitse training datasettiä."""
    from src.dataset_builder import get_dataset_stats, export_as_jsonl

    stats = get_dataset_stats()
    console.print(Panel(
        f"Yhteensä:       [bold]{stats['total']}[/bold]\n"
        f"Tarkistettu:    [green]{stats['verified']}[/green]\n"
        f"Tarkistamaton:  [yellow]{stats['unverified']}[/yellow]\n"
        f"Valmistajat:    {stats['manufacturers']}",
        title="Training Dataset",
    ))

    if vie:
        path = export_as_jsonl(verified_only=not kaikki)
        console.print(f"[green]Viety:[/green] {path}")
        count = stats["total"] if kaikki else stats["verified"]
        console.print(f"  {count} esimerkkiä JSONL-formaatissa fine-tuningia varten.")


@cli.command("tarkista")
@click.argument("example_path", type=click.Path(exists=True))
def cmd_tarkista(example_path):
    """
    Tarkista ja merkitse training-esimerkki oikeaksi.
    Käytä tätä kun olet manuaalisesti tarkistanut puretut arvot.
    """
    path = Path(example_path)
    with open(path, encoding="utf-8") as f:
        ex = json.load(f)

    console.print(f"Esimerkki: [cyan]{path.name}[/cyan]")
    console.print(f"Kone: {ex['metadata'].get('unit_code')}  "
                  f"Valmistaja: {ex['metadata'].get('manufacturer')}")
    console.print("\nPurettu data:")
    console.print(json.dumps(ex["output"], ensure_ascii=False, indent=2))

    if Confirm.ask("\nMerkitäänkö tarkistetuksi?"):
        ex["metadata"]["verified"] = True
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ex, f, ensure_ascii=False, indent=2)
        console.print(f"[green]Merkitty tarkistetuksi.[/green]")
    else:
        console.print("[yellow]Ei muutoksia.[/yellow]")


@cli.command("mallit")
def cmd_mallit():
    """Listaa ja hallitse Ollama-malleja."""
    from src.llm_extractor import check_ollama_running, list_available_models
    import subprocess

    if not check_ollama_running():
        console.print("[red]Ollama ei käynnissä.[/red] Käynnistä: [yellow]ollama serve[/yellow]")
        return

    models = list_available_models()
    console.print(f"\nSaatavilla olevat mallit ({len(models)} kpl):")
    for m in models:
        console.print(f"  • {m}")

    console.print("\n[dim]Suositellut mallit tähän tehtävään:[/dim]")
    recommended = [
        ("mistral", "7B, hyvä tarkkuus, ~4GB"),
        ("llama3.1", "8B, erinomainen, ~5GB"),
        ("phi3.5", "3.8B, nopea, ~2.5GB"),
        ("qwen2.5:7b", "7B, erittäin hyvä JSON, ~4GB"),
    ]
    for name, desc in recommended:
        installed = "[green]✓[/green]" if any(name in m for m in models) else "  "
        console.print(f"  {installed} {name:<15} {desc}")

    console.print("\nLataa malli: [yellow]ollama pull mistral[/yellow]")


# ── Ohjelman käynnistys ───────────────────────────────────────────────────────

def main():
    """
    Käynnistyspiste.
    Tukee oikopolkua: python main.py TK01.pdf
    (muunnetaan automaattisesti → python main.py purku TK01.pdf)
    """
    args = sys.argv[1:]

    # Oikopolku: jos ensimmäinen argumentti on PDF-tiedosto
    if (args and args[0].lower().endswith(".pdf")
            and not args[0].startswith("-")):
        sys.argv.insert(1, "purku")

    cli()


if __name__ == "__main__":
    main()
