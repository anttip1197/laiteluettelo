"""
Laiteluettelo - Laitetyyppien tietomalli
Pydantic-mallit validointiin ja tyyppiturvallisuuteen.
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, field_validator
import yaml
from pathlib import Path


def load_equipment_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "equipment_types.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class ComponentRow(BaseModel):
    """Yksi rivi laiteluettelossa (LTO:lla kaksi riviä)."""
    row_label: Optional[str] = None  # "Tulopuoli" / "Poistopuoli"
    data: dict[str, Any] = {}        # kenttäavain -> arvo


class ExtractedComponent(BaseModel):
    """Yksi laite/komponentti koneajokorteista purettuna."""
    code: str                         # Esim. "SP01", "LTO10"
    type_prefix: str                  # Esim. "SP", "LTO", "TF"
    name: str                         # Esim. "Sulkupelti"
    side: str                         # "supply" | "exhaust" | "both"
    rows: list[ComponentRow] = []
    notes: Optional[str] = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        allowed = {"supply", "exhaust", "both"}
        if v not in allowed:
            raise ValueError(f"side must be one of {allowed}")
        return v


class ExtractedUnit(BaseModel):
    """Koko IV-kone purettuna."""
    unit_code: str                        # Esim. "TK01"
    project: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    components: list[ExtractedComponent] = []
    raw_supply_airflow: Optional[float] = None   # m³/s
    raw_exhaust_airflow: Optional[float] = None  # m³/s
    source_pdf: Optional[str] = None


class ExtractionResult(BaseModel):
    """LLM:n palauttama raakadata — validoidaan tähän."""
    unit_code: str
    project: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    supply_airflow: Optional[float] = None
    exhaust_airflow: Optional[float] = None
    components: list[dict] = []


def get_type_config(type_prefix: str) -> Optional[dict]:
    """Hae laitetyypin konfiguraatio YAML:sta."""
    config = load_equipment_config()
    return config["equipment_types"].get(type_prefix)


def get_all_type_prefixes() -> list[str]:
    config = load_equipment_config()
    return list(config["equipment_types"].keys())


def get_default_code(side: str, type_prefix: str) -> str:
    """Palauta oletuslaitekoodi (esim. SP01, TF30)."""
    config = load_equipment_config()
    scheme = config.get("default_code_scheme", {})
    return scheme.get(side, {}).get(type_prefix, f"{type_prefix}??")
