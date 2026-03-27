"""
Laiteluettelo - Training dataset -keräin
Tallentaa onnistuneet ekstraktoinnit myöhempää fine-tuningia varten.
Jokainen esimerkki on (PDF-teksti, JSON-vastaus) -pari.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .equipment_schema import ExtractedUnit

DATASET_DIR = Path(__file__).parent.parent / "training" / "examples"


def save_example(
    pdf_text: str,
    extracted_unit: ExtractedUnit,
    verified: bool = False,
    notes: Optional[str] = None,
) -> Path:
    """
    Tallenna yksi training-esimerkki JSON-tiedostoon.

    verified=True: ihminen on tarkistanut ja korjannut arvot
    verified=False: automaattinen ekstraktointi, ei tarkistettu
    """
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{extracted_unit.unit_code}_{timestamp}.json"

    # Muunna ExtractedUnit takaisin LLM-formaattiin (input/output -pari)
    output_json = _unit_to_llm_format(extracted_unit)

    example = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "unit_code": extracted_unit.unit_code,
            "project": extracted_unit.project,
            "manufacturer": extracted_unit.manufacturer,
            "model": extracted_unit.model,
            "source_pdf": extracted_unit.source_pdf,
            "verified": verified,
            "notes": notes,
        },
        "input": pdf_text[:8000],  # Rajoita tallennuskoko
        "output": output_json,
    }

    path = DATASET_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(example, f, ensure_ascii=False, indent=2)

    return path


def _unit_to_llm_format(unit: ExtractedUnit) -> dict:
    """Muunna ExtractedUnit takaisin LLM-outputin muotoon."""
    components = []
    for comp in unit.components:
        if comp.type_prefix == "LTO" and len(comp.rows) == 2:
            supply_data = comp.rows[0].data.copy()
            exhaust_data = comp.rows[1].data.copy()
            # Siirrä jaetut kentät omaan osioon
            shared = {}
            if "hyotysuhde_en308" in supply_data:
                shared["hyotysuhde_en308"] = supply_data.pop("hyotysuhde_en308")

            components.append({
                "type": comp.type_prefix,
                "side": comp.side,
                "supply_data": supply_data,
                "exhaust_data": exhaust_data,
                "shared": shared,
            })
        else:
            data = comp.rows[0].data if comp.rows else {}
            components.append({
                "type": comp.type_prefix,
                "side": comp.side,
                "data": data,
            })

    return {
        "unit_code": unit.unit_code,
        "project": unit.project,
        "manufacturer": unit.manufacturer,
        "model": unit.model,
        "supply_airflow": unit.raw_supply_airflow,
        "exhaust_airflow": unit.raw_exhaust_airflow,
        "components": components,
    }


def load_all_examples(verified_only: bool = False) -> list[dict]:
    """Lataa kaikki tallennetut esimerkit."""
    examples = []
    for path in DATASET_DIR.glob("*.json"):
        with open(path, encoding="utf-8") as f:
            example = json.load(f)
        if verified_only and not example["metadata"].get("verified"):
            continue
        examples.append(example)
    return examples


def export_as_jsonl(output_path: Optional[Path] = None, verified_only: bool = True) -> Path:
    """
    Vie dataset JSONL-formaattiin fine-tuningia varten.
    Jokainen rivi on: {"prompt": ..., "completion": ...}
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent / "training" / "dataset.jsonl"

    examples = load_all_examples(verified_only=verified_only)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in examples:
            line = {
                "prompt": ex["input"],
                "completion": json.dumps(ex["output"], ensure_ascii=False),
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    return output_path


def get_dataset_stats() -> dict:
    """Palauta tilastot datasetistä."""
    all_examples = load_all_examples(verified_only=False)
    verified = [e for e in all_examples if e["metadata"].get("verified")]
    manufacturers = {}
    for ex in all_examples:
        mfr = ex["metadata"].get("manufacturer") or "Tuntematon"
        manufacturers[mfr] = manufacturers.get(mfr, 0) + 1

    return {
        "total": len(all_examples),
        "verified": len(verified),
        "unverified": len(all_examples) - len(verified),
        "manufacturers": manufacturers,
    }
