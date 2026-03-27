# Training Dataset - Ohjeet

## Rakenne

Jokainen esimerkki on JSON-tiedosto kansiossa `training/examples/`.

```
{
  "metadata": {
    "unit_code": "TK01",
    "manufacturer": "Systemair",
    "verified": true/false   ← TÄRKEÄ: tarkistettu = luotettava data
  },
  "input":  "< PDF:stä purettu teksti >",
  "output": "< oikea JSON-rakenne >"
}
```

## Miten kerätä uusia esimerkkejä

1. **Aja purku tallennusmoodissa:**
   ```
   python main.py TK01_uusi.pdf --tallenna-esimerkki --tarkista
   ```
   `--tarkista` näyttää puretut arvot ja kysyy hyväksynnän.
   Jos hyväksyt → `verified: true` automaattisesti.

2. **Tarkista myöhemmin:**
   ```
   python main.py tarkista training/examples/TK01_xxx.json
   ```

3. **Näytä tilastot:**
   ```
   python main.py dataset
   ```

## Milloin fine-tunata?

| Tarkistetut esimerkit | Suositus |
|-----------------------|----------|
| < 10                  | Käytä pelkkää prompt engineeringiä (oletustoiminta) |
| 10–30                 | Fine-tuning parantaa jo merkittävästi |
| 30–100                | Erittäin hyvä tarkkuus |
| 100+                  | Mallin voi deploytata itsenäisesti |

## Valmistajat — kerää monipuolisesti

Tavoite: vähintään 3–5 esimerkkiä per valmistaja.

- [ ] Systemair (Geniox) — 1 esimerkki ✓
- [ ] Fläkt Woods / Fläkt Group
- [ ] Swegon (GOLD)
- [ ] Koja / Kojair
- [ ] Climecon
- [ ] Ilmateho
- [ ] Muut

## Fine-tuning

```bash
# Vie dataset JSONL-formaattiin
python main.py dataset --vie

# Treeniä (vaatii Unsloth-asennuksen)
python training/fine_tune.py --base-model unsloth/Phi-3.5-mini-instruct --epochs 3

# Vie Ollama-mallina
python training/fine_tune.py --export-ollama

# Käytä fine-tunattua mallia
python main.py TK01.pdf --model laiteluettelo
```
