"""
Laiteluettelo - LLM-pohjainen tiedonpurku Ollaman kautta.
Lähettää koneajokortin tekstin paikalliselle mallille ja saa takaisin jäsennellyn JSON:in.
"""
from __future__ import annotations
import json
import re
import time
from typing import Optional
import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .equipment_schema import (
    ExtractionResult,
    ExtractedUnit,
    ExtractedComponent,
    ComponentRow,
    get_type_config,
    get_default_code,
    get_all_type_prefixes,
    load_equipment_config,
)

console = Console()

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "mistral"  # tai "phi3.5", "llama3.2"

# Pääprompt — selittää mallille mitä purkaa
SYSTEM_PROMPT = """You are an expert HVAC engineering assistant specializing in Finnish ventilation systems (ilmanvaihto).
Your task: extract structured technical data from ventilation unit specification sheets (koneajokortti).

IMPORTANT: Return ONLY valid JSON. No explanations, no markdown, no code blocks. Pure JSON only.

Component types and what to extract:

SP (sulkupelti / shut-off damper):
  - ilma_dp: air pressure drop in Pa (number only)

FG (peltimoottori / damper actuator):
  - No technical data needed, leave data empty {}

SU (suodatin / air filter):
  - ilma_dp_mitoitus: design pressure drop Pa
  - ilma_dp_alku: initial/clean pressure drop Pa
  - ilma_dp_loppu: final/dirty pressure drop Pa
  - suodatinluokka: filter class string e.g. "ePM1 60% (F7)"

LTO (lämmöntalteenotto / heat recovery):
  MUST have two separate data sets - supply side AND exhaust side:
  supply_data:
    - ilma_dp: supply air pressure drop Pa
    - ilma_lampotila_ennen: supply air temperature before LTO (°C, winter condition)
    - ilma_lampotila_jalkeen: supply air temperature after LTO (°C, winter condition)
  exhaust_data:
    - ilma_dp: exhaust air pressure drop Pa
    - ilma_lampotila_ennen: exhaust air temperature before LTO (°C, winter condition)
    - ilma_lampotila_jalkeen: exhaust air temperature after LTO (°C, winter condition)
  shared:
    - hyotysuhde_en308: thermal efficiency % (dry, EN308) — single value for both sides

TF (puhallin / fan):
  - ilmamaara: airflow m³/s
  - mitoituspaine: external static pressure Pa (kanavistopaine)
  - sahkoteho: actual power consumption kW (not nominal motor power rating)
  - jannite_virta: string like "3x400V / 5.4A"

LP (lämmityspatteri / heating coil):
  - nestevirta: water flow l/s
  - neste_dp: water pressure drop kPa
  - ilma_dp: air pressure drop Pa
  - ilma_lampotila_ennen: air temperature before coil °C (winter design)
  - ilma_lampotila_jalkeen: air temperature after coil °C (winter design)
  - neste_meno: supply water temperature °C
  - neste_paluu: return water temperature °C

JP (jäähdytyspatteri / cooling coil):
  - nestevirta: water flow l/s
  - neste_dp: water pressure drop kPa
  - ilma_dp: WET coil air pressure drop Pa (märkä patteri)
  - ilma_lampotila_ennen: air temperature before coil °C (summer design)
  - ilma_lampotila_jalkeen: air temperature after coil °C (summer design)
  - neste_meno: chilled water supply temperature °C
  - neste_paluu: chilled water return temperature °C

AV (äänenvaimennin / silencer):
  - ilma_dp: air pressure drop Pa

Return this exact JSON structure:
{
  "unit_code": "TK01",
  "project": "project name or null",
  "manufacturer": "manufacturer name or null",
  "model": "model name or null",
  "supply_airflow": 1.68,
  "exhaust_airflow": 1.75,
  "components": [
    {
      "type": "SP",
      "side": "supply",
      "data": { "ilma_dp": 3 }
    },
    {
      "type": "FG",
      "side": "supply",
      "data": {}
    },
    {
      "type": "SU",
      "side": "supply",
      "data": {
        "ilma_dp_mitoitus": 110,
        "ilma_dp_alku": 60,
        "ilma_dp_loppu": 160,
        "suodatinluokka": "ePM1 60% (F7)"
      }
    },
    {
      "type": "LTO",
      "side": "both",
      "supply_data": {
        "ilma_dp": 149,
        "ilma_lampotila_ennen": -29.0,
        "ilma_lampotila_jalkeen": 15.3
      },
      "exhaust_data": {
        "ilma_dp": 159,
        "ilma_lampotila_ennen": 22.0,
        "ilma_lampotila_jalkeen": -4.5
      },
      "shared": {
        "hyotysuhde_en308": 84.5
      }
    },
    {
      "type": "TF",
      "side": "supply",
      "data": {
        "ilmamaara": 1.68,
        "mitoituspaine": 300,
        "sahkoteho": 2.27,
        "jannite_virta": "3x400V / 5.4A"
      }
    }
  ]
}"""


def check_ollama_running() -> bool:
    """Tarkista onko Ollama käynnissä."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def list_available_models() -> list[str]:
    """Listaa Ollamassa saatavilla olevat mallit."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def select_best_model() -> str:
    """Valitse paras saatavilla oleva malli."""
    available = list_available_models()
    # Paremmuusjärjestys tähän tehtävään
    preferred = ["mistral", "llama3.1", "llama3", "phi3.5", "phi3", "gemma2", "qwen2.5"]
    for pref in preferred:
        for avail in available:
            if pref in avail.lower():
                return avail
    return available[0] if available else DEFAULT_MODEL


def call_ollama(prompt: str, model: str, max_retries: int = 3) -> Optional[str]:
    """Kutsu Ollama API:a ja palauta vastaus."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 4096,
        }
    }

    for attempt in range(max_retries):
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=300
            )
            r.raise_for_status()
            return r.json().get("response", "")
        except requests.exceptions.Timeout:
            console.print(f"[yellow]Aikakatkaisu, yritys {attempt+1}/{max_retries}...[/yellow]")
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Virhe: {e}[/red]")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)
    return None


def build_extraction_prompt(pdf_text: str, unit_code: Optional[str] = None) -> str:
    """Rakenna täydellinen prompti PDF-tekstille."""
    # Rajoita tekstin pituus (mallit eivät hyödy tarpeettomasta tekstistä)
    max_chars = 12000
    if len(pdf_text) > max_chars:
        pdf_text = pdf_text[:max_chars] + "\n...[teksti katkaistu]"

    unit_hint = f"Unit code appears to be: {unit_code}\n" if unit_code else ""

    return f"""{SYSTEM_PROMPT}

---
{unit_hint}Extract all components from the following ventilation unit specification sheet text:

{pdf_text}
---

Remember: Return ONLY valid JSON. Extract ALL components found in both supply and exhaust sides."""


def parse_llm_response(response_text: str) -> Optional[dict]:
    """Parsii LLM:n JSON-vastauksen, sietää pieniä virheitä."""
    if not response_text:
        return None

    # Poista mahdolliset markdown-koodiblokki-merkit
    cleaned = re.sub(r"```json\s*", "", response_text)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Yritä löytää JSON objekti tekstistä
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def build_extracted_unit(raw: dict, source_pdf: str = "") -> ExtractedUnit:
    """
    Muunna LLM:n raaka-JSON validoiduksi ExtractedUnit-olioksi.
    Lisää automaattiset laitekoodit ja normalisoi rakenne.
    """
    config = load_equipment_config()
    scheme = config.get("default_code_scheme", {})

    # Seuraa jo käytetyt koodit
    used_codes: dict[str, int] = {}

    components: list[ExtractedComponent] = []

    for comp_raw in raw.get("components", []):
        type_prefix = comp_raw.get("type", "").upper()
        side = comp_raw.get("side", "supply")

        # Automaattinen koodinanto
        scheme_side = "exhaust" if side == "exhaust" else "supply"
        base_code = scheme.get(scheme_side, {}).get(type_prefix)
        if not base_code:
            base_code = f"{type_prefix}XX"

        # Jos koodi jo käytössä, lisää numero
        if base_code in used_codes:
            used_codes[base_code] += 1
            code = f"{type_prefix}{used_codes[base_code]:02d}"
        else:
            used_codes[base_code] = 1
            code = base_code

        type_cfg = get_type_config(type_prefix) or {}
        name = type_cfg.get("name", type_prefix)

        # Muodosta rivi(t) — LTO:lla erikoiskäsittely
        rows: list[ComponentRow] = []

        if type_prefix == "LTO":
            supply_data = comp_raw.get("supply_data", {})
            exhaust_data = comp_raw.get("exhaust_data", {})
            shared = comp_raw.get("shared", {})

            # Lisää jaetut tiedot tulopuolen dataan
            supply_combined = {**supply_data, **shared}
            rows.append(ComponentRow(row_label="Tulopuoli", data=supply_combined))
            rows.append(ComponentRow(row_label="Poistopuoli", data=exhaust_data))
        else:
            data = comp_raw.get("data", {})
            rows.append(ComponentRow(data=data))

        components.append(ExtractedComponent(
            code=code,
            type_prefix=type_prefix,
            name=name,
            side=side,
            rows=rows,
        ))

    return ExtractedUnit(
        unit_code=raw.get("unit_code", "TK??"),
        project=raw.get("project"),
        manufacturer=raw.get("manufacturer"),
        model=raw.get("model"),
        components=components,
        raw_supply_airflow=raw.get("supply_airflow"),
        raw_exhaust_airflow=raw.get("exhaust_airflow"),
        source_pdf=source_pdf,
    )


def extract_from_pdf_text(
    pdf_text: str,
    unit_code: Optional[str] = None,
    model: Optional[str] = None,
    source_pdf: str = "",
) -> ExtractedUnit:
    """
    Pääfunktio: PDF-teksti → ExtractedUnit.
    Tarkistaa Ollaman, valitsee mallin, kutsuu API:a.
    """
    if not check_ollama_running():
        raise RuntimeError(
            "Ollama ei ole käynnissä!\n"
            "Käynnistä komennolla: ollama serve\n"
            "Asenna osoitteesta: https://ollama.com"
        )

    if model is None:
        model = select_best_model()
        console.print(f"[dim]Käytetään mallia: {model}[/dim]")

    prompt = build_extraction_prompt(pdf_text, unit_code)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Puretaan koneajokortti mallilla {model}...", total=None)
        raw_response = call_ollama(prompt, model)
        progress.update(task, completed=True)

    if not raw_response:
        raise ValueError("LLM ei palauttanut vastausta.")

    parsed = parse_llm_response(raw_response)
    if not parsed:
        raise ValueError(
            f"LLM:n vastaus ei ole kelvollista JSON:ia:\n{raw_response[:500]}"
        )

    return build_extracted_unit(parsed, source_pdf=source_pdf)
