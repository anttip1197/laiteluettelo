"""
Laiteluettelo - PDF-tekstin purku
Tukee useita valmistajia: Systemair, Fläkt, Swegon, Koja jne.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
import pdfplumber


# Tunnetut valmistajat ja niiden tunnistamiseen käytetyt hakusanat
KNOWN_MANUFACTURERS = {
    "Systemair": ["systemair", "systemaircad", "geniox"],
    "Fläkt": ["flakt", "fläkt woods", "flaktwoods"],
    "Swegon": ["swegon", "gold"],
    "Koja": ["koja", "kojair"],
    "Climecon": ["climecon"],
    "Ilmateho": ["ilmateho"],
}


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Pura PDF:n teksti yhdeksi merkkijonoksi."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF ei löydy: {pdf_path}")

    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                pages_text.append(f"--- Sivu {i+1} ---\n{text}")

    full_text = "\n\n".join(pages_text)
    return full_text


def extract_pages_as_list(pdf_path: str | Path) -> list[str]:
    """Pura PDF sivuittain listaksi."""
    pdf_path = Path(pdf_path)
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            pages.append(text)
    return pages


def detect_manufacturer(text: str) -> Optional[str]:
    """Tunnista valmistaja tekstistä."""
    text_lower = text.lower()
    for manufacturer, keywords in KNOWN_MANUFACTURERS.items():
        if any(kw in text_lower for kw in keywords):
            return manufacturer
    return None


def detect_unit_code(text: str) -> Optional[str]:
    """Etsi IV-koneen tunnus tekstistä (esim. TK01, TK-01, IV01)."""
    # Systemair-tyyli: "Kone nro. TK01" tai "Kone nro. TK01/Asunnot"
    patterns = [
        r"Kone\s+nro\.?\s*[:\.]?\s*(TK\d+)",
        r"Kone\s+nro\.?\s*[:\.]?\s*(IV\d+)",
        r"\b(TK[-\s]?\d{2,3})\b",
        r"\b(IV[-\s]?\d{2,3})\b",
        r"Ilmanvaihtokone[^\n]*\s+(TK\d+)",
        r"Unit\s+(?:code|no\.?)[:\s]+(TK\d+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).replace(" ", "").replace("-", "")
    return None


def detect_project(text: str) -> Optional[str]:
    """Etsi projektin nimi."""
    patterns = [
        r"Projekti\s*[:\.]?\s*(.+?)(?:\n|Kone)",
        r"Project\s*[:\.]?\s*(.+?)(?:\n)",
        r"Kohde\s*[:\.]?\s*(.+?)(?:\n)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def split_into_sections(text: str) -> dict[str, str]:
    """
    Jaa koneajokortti osioihin valmistajan rakenteen mukaan.
    Systemair: "Tuloilmakone sisältää" / "Poistoilmakone sisältää"
    Palauttaa dict: {"supply": teksti, "exhaust": teksti, "general": teksti}
    """
    sections = {"supply": "", "exhaust": "", "general": text}

    # Systemair-rakenne
    supply_match = re.search(
        r"Tuloilmakone\s+sisält[äa][äa](.+?)(?=Poistoilmakone\s+sisält|$)",
        text, re.IGNORECASE | re.DOTALL
    )
    exhaust_match = re.search(
        r"Poistoilmakone\s+sisält[äa][äa](.+?)$",
        text, re.IGNORECASE | re.DOTALL
    )

    if supply_match:
        sections["supply"] = supply_match.group(1)
    if exhaust_match:
        sections["exhaust"] = exhaust_match.group(1)

    return sections


def get_pdf_metadata(pdf_path: str | Path) -> dict:
    """Kerää perustiedot PDF:stä."""
    pdf_path = Path(pdf_path)
    text = extract_text_from_pdf(pdf_path)
    return {
        "filename": pdf_path.name,
        "manufacturer": detect_manufacturer(text),
        "unit_code": detect_unit_code(text),
        "project": detect_project(text),
        "text_length": len(text),
        "sections": split_into_sections(text),
    }
