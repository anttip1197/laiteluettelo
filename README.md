# LVI Laiteluettelo — Automaattinen koneajokorttipurku

Työkalu, joka lukee ilmanvaihtokoneen koneajokortin PDF:n ja täyttää laiteluettelon automaattisesti.
Toimii **täysin paikallisesti** — tiedot eivät lähde minnekään nettiin.

---

## Mitä ohjelma tekee

1. Luet PDF:n ohjelmalle (`python main.py TK01.pdf`)
2. Paikallinen kielimalli (AI) lukee koneajokortin ja poimii sieltä tekniset tiedot
3. Ohjelma luo valmiin **Excel-tiedoston** laiteluettelosta

**Poimittavat laitteet ja tiedot:**

| Laitetyyppi | Mitä poimitaan |
|---|---|
| **SP** Sulkupelti | Ilman painehäviö (Pa) |
| **FG** Peltimoottori | Ei mitoitustietoja |
| **SU** Suodatin | Painehäviöt: mitoitus / alku / loppu (Pa), suodatinluokka |
| **LTO** Lämmöntalteenotto | Ilman lämpötilat ennen/jälkeen (°C), painehäviö (Pa), hyötysuhde EN308 (%) — **kaksi riviä: tulo- ja poistopuoli** |
| **TF** Puhallin | Ilmamäärä (m³/s), paine (Pa), sähköteho (kW), jännite/virta |
| **LP** Lämmityspatteri | Nestevirta (l/s), nestepaine (kPa), ilmapaine (Pa), lämpötilat |
| **JP** Jäähdytyspatteri | Nestevirta (l/s), nestepaine (kPa), ilmapaine (Pa), lämpötilat |
| **ÄV** Äänenvaimennin | Ilman painehäviö (Pa) |

**Tuetut valmistajat:** Systemair, Fläkt, Swegon, Koja, Climecon, Ilmateho
*(Muut valmistajat toimivat usein myös, AI tunnistaa rakenteen)*

---

## Vaatimukset

- **Windows 10/11** (64-bit)
- **Python 3.10 tai uudempi**
- **Ollama** (paikallinen AI-alusta)
- ~5 GB vapaata levytilaa (AI-malli)
- 8 GB RAM vähintään (suositus 16 GB+)

---

## Asennus — vaihe vaiheelta

### Vaihe 1 — Lataa tämä ohjelma

Klikkaa tällä sivulla vihreää **Code**-nappia → **Download ZIP**
Pura ZIP esimerkiksi kansioon `C:\laiteluettelo\`

*TAI jos sinulla on Git asennettuna:*
```
git clone https://github.com/anttip1197/laiteluettelo.git
cd laiteluettelo
```

---

### Vaihe 2 — Asenna Python

1. Mene osoitteeseen **https://www.python.org/downloads/**
2. Lataa uusin Python 3.x (esim. 3.12)
3. Asenna — **muista rastittaa "Add Python to PATH"** asennuksen alussa

Tarkista asennus avaamalla komentokehote (`Win + R` → `cmd`) ja kirjoita:
```
python --version
```
Pitäisi näyttää esim. `Python 3.12.0`

---

### Vaihe 3 — Asenna Ollama (paikallinen AI)

1. Mene osoitteeseen **https://ollama.com**
2. Klikkaa **Download** ja asenna
3. Avaa komentokehote ja lataa AI-malli:

```
ollama pull mistral
```

> Tämä lataa ~4 GB tiedoston. Lataus tehdään vain kerran.

Tarkista että Ollama toimii:
```
ollama list
```
Pitäisi näyttää `mistral` listalla.

---

### Vaihe 4 — Asenna ohjelman riippuvuudet

Avaa komentokehote ohjelman kansiossa:
```
cd C:\laiteluettelo
pip install -r requirements.txt
```

*Tai kaksoisklikkaa `install.bat` — se tekee kaiken automaattisesti.*

---

### Vaihe 5 — Tarkista asennus

```
python main.py status
```

Pitäisi näyttää:
```
● Ollama: käynnissä
  ★ mistral:latest
Training dataset: 1 esimerkkiä (1 tarkistettu / 0 tarkistamaton)
```

---

## Käyttö

### Perusajo — luo laiteluettelo PDF:stä

```
python main.py TK01.pdf
```

Ohjelma avaa valmiin Excel-tiedoston automaattisesti.
Excel tallennetaan kansioon `output\laiteluettelo_TK01.xlsx`

---

### Tarkistusajo — näytä tiedot ennen tallennusta

```
python main.py TK01.pdf --tarkista
```

Ohjelma näyttää puretut tiedot taulukossa ja kysyy hyväksynnän ennen kuin tallentaa Excelin.
Hyödyllinen kun haluat varmistaa että AI löysi oikeat arvot.

---

### Kerää training-dataa (parantaa ohjelmaa ajan myötä)

```
python main.py TK01.pdf --tarkista --tallenna-esimerkki
```

Kun hyväksyt tiedot, ne tallentuvat ohjelman oppimateriaaliksi.
Mitä enemmän esimerkkejä kertyy, sitä tarkemmin ohjelma oppii.

---

### Muut komennot

```bash
# Tarkista Ollaman tila ja saatavilla olevat mallit
python main.py status

# Näytä kerätyn training-datan tilastot
python main.py dataset

# Listaa ja vertaile AI-malleja
python main.py mallit

# Käytä tiettyä mallia (jos sinulla on useita)
python main.py TK01.pdf --model phi3.5

# Tallenna Excel tiettyyn kansioon
python main.py TK01.pdf --output C:\Projektit\Koirasaarentie\
```

---

## Excel-tiedoston rakenne

Ohjelma luo Excel-tiedoston jossa on:

- **Otsikkorivi** — projektin nimi, konekoodi, päivämäärä, ilmavirrat
- **Värikoodatut rivit** per laitetyyppi:
  - 🟢 Vihreä — Sulkupelti (SP)
  - 🟡 Keltainen — Suodatin (SU)
  - 🔵 Sininen — LTO tulopuoli
  - 🟣 Violetti — LTO poistopuoli
  - 🟠 Oranssi — Puhallin (TF)
  - 🩷 Pinkki — Lämmityspatteri (LP)
  - 🩵 Syaani — Jäähdytyspatteri (JP)
  - 🌸 Roosa — Äänenvaimennin (ÄV)

Excel on tarkoitettu kopioitavaksi viralliseen projektipohjaan.

---

## Uuden laitetyypin lisääminen

Avaa tiedosto `config/equipment_types.yaml` tekstieditorilla ja lisää uusi lohko:

```yaml
  LPE:
    name: "Sähkölämmityspatteri"
    name_en: "Electric heating coil"
    rows: 1
    fields:
      - key: sahkoteho
        label: "Teho (kW)"
        unit: "kW"
        extract_hint: "sähköteho / electric power"
      - key: jannite
        label: "Jännite (V)"
        unit: "V"
        extract_hint: "jännite / voltage"
```

Ei tarvita muutoksia Python-koodiin. Ohjelma tunnistaa uuden tyypin automaattisesti.

---

## Vianetsintä

### "Ollama ei ole käynnissä"

Käynnistä Ollama manuaalisesti:
```
ollama serve
```
Jätä tämä ikkuna auki ja aja ohjelma uudessa komentokehotteessa.

---

### "Ei malleja"

Lataa malli:
```
ollama pull mistral
```

---

### "PDF ei löydy"

Tarkista että kirjoitat oikean polun. Jos tiedostossa on välilyöntejä, laita lainausmerkit:
```
python main.py "C:\Projektit\TK01 koneajokortti.pdf"
```

---

### AI poimii väärät arvot

1. Käytä `--tarkista`-lippu — näet arvot ennen tallennusta
2. Jos malli on heikko, vaihda parempaan:
   ```
   ollama pull llama3.1
   python main.py TK01.pdf --model llama3.1
   ```
3. Kerää lisää training-esimerkkejä (katso alla)

---

### Pip install epäonnistuu

Kokeile:
```
pip install -r requirements.txt --user
```

---

## Training-datan keräys ja ohjelman kehitys

Ohjelman tarkkuus paranee kun sille opetetaan lisää esimerkkejä.

### Miten kerätä esimerkkejä

```bash
# Aja purku tarkistus+tallennus-moodissa
python main.py TK01_uusi.pdf --tarkista --tallenna-esimerkki
```

Ohjelma näyttää puretut tiedot. Jos ne ovat oikein → hyväksy → tallennetaan.
Esimerkit tallennetaan kansioon `training/examples/`.

### Tilastot

```
python main.py dataset
```

### Milloin kannattaa "opettaa" malli uudelleen?

| Tarkistettuja esimerkkejä | Suositus |
|---|---|
| 0–10 | Käytä ohjelmaa normaalisti, kerää esimerkkejä |
| 10–30 | Harkitse fine-tuningia (merkittävä tarkkuusparannus) |
| 30+ | Fine-tuning kannattaa ehdottomasti |

### Fine-tuning (vaatii lisäasennuksia)

```bash
# Asenna fine-tuning-kirjasto
pip install unsloth

# Treeniä
python training/fine_tune.py --epochs 3

# Vie malli Ollamaan
python training/fine_tune.py --export-ollama

# Käytä omaa mallia
python main.py TK01.pdf --model laiteluettelo
```

---

## Projektikansion rakenne

```
laiteluettelo/
├── main.py                      ← Pääohjelma, tästä ajetaan
├── requirements.txt             ← Python-kirjastot
├── install.bat                  ← Asennusskripti (Windows)
│
├── config/
│   └── equipment_types.yaml     ← Laitetyypit — muokkaa tätä lisätäksesi tyyppejä
│
├── src/                         ← Ohjelman ydin (ei tarvitse muokata)
│   ├── pdf_extractor.py
│   ├── llm_extractor.py
│   ├── excel_generator.py
│   ├── equipment_schema.py
│   └── dataset_builder.py
│
├── training/
│   ├── examples/                ← Training-esimerkit tallennetaan tänne
│   ├── fine_tune.py             ← Fine-tuning-skripti
│   └── README_DATASET.md
│
└── output/                      ← Valmiit Excel-tiedostot tallennetaan tänne
```

---

## Tekniset tiedot

- **AI-malli:** Mistral 7B (tai muu Ollama-yhteensopiva malli)
- **PDF-purku:** pdfplumber
- **Excel-generointi:** openpyxl
- **Fine-tuning:** Unsloth + LoRA (ei pakollinen)
- **Kieli:** Python 3.10+

---

## Lisenssi

MIT — vapaa käyttää, muokata ja jakaa.

---

## Palaute ja kehitys

Löysitkö bugin tai haluatko ehdottaa uutta ominaisuutta?
Avaa **Issue** tällä GitHub-sivulla.
