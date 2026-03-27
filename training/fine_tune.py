"""
Laiteluettelo - Fine-tuning skripti
Treeniä pienelle mallille Unsloth-kirjastolla (tehokas LoRA).

Vaatimukset:
  pip install unsloth
  pip install torch --index-url https://download.pytorch.org/whl/cu121  (CUDA)

  TAI CPU-only (hidas mutta toimii):
  pip install unsloth[cpu]

Käyttö:
  python training/fine_tune.py                          # Käytä oletusasetuksia
  python training/fine_tune.py --base-model unsloth/Phi-3.5-mini-instruct
  python training/fine_tune.py --epochs 3 --batch-size 2
  python training/fine_tune.py --export-ollama          # Vie Ollama-mallina
"""
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
OUTPUT_DIR = Path(__file__).parent / "model_output"

# Suositellut mallit (pienimmästä suurimpaan)
RECOMMENDED_MODELS = {
    "phi3.5":   "unsloth/Phi-3.5-mini-instruct",        # 3.8B — nopein, toimii CPU:lla
    "mistral":  "unsloth/mistral-7b-instruct-v0.3",     # 7B — paras tarkkuus
    "llama3.2": "unsloth/Llama-3.2-3B-Instruct",        # 3B — hyvä kompromissi
    "qwen2.5":  "unsloth/Qwen2.5-7B-Instruct",          # 7B — erinomainen JSON
}

SYSTEM_PROMPT = """You are an expert HVAC engineering assistant specializing in Finnish ventilation systems.
Extract structured technical data from ventilation unit specification sheets and return valid JSON only."""


def load_dataset(path: Path, verified_only: bool = True) -> list[dict]:
    """Lataa JSONL-datasetti."""
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    console.print(f"Ladattu {len(examples)} esimerkkiä tiedostosta {path.name}")
    return examples


def format_for_training(examples: list[dict]) -> list[dict]:
    """
    Muotoile esimerkit Alpaca/chat-formaattiin fine-tuningia varten.
    """
    formatted = []
    for ex in examples:
        prompt = ex["prompt"]
        completion = ex["completion"]

        # Chat-formaatti
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract all components from this specification sheet:\n\n{prompt}"},
            {"role": "assistant", "content": completion},
        ]
        formatted.append({"messages": messages})
    return formatted


@click.command()
@click.option("--base-model", default="unsloth/Phi-3.5-mini-instruct",
              help="Pohjamallin nimi Hugging Facesta")
@click.option("--epochs", default=3, help="Treeniepookkien määrä")
@click.option("--batch-size", default=2, help="Batch-koko (vähennä jos muisti loppuu)")
@click.option("--lora-rank", default=16, help="LoRA rank (16=nopea, 64=tarkempi)")
@click.option("--learning-rate", default=2e-4, help="Oppimisnopeus")
@click.option("--export-ollama", is_flag=True, help="Vie malli Ollama-formaattiin")
@click.option("--kaikki", is_flag=True, help="Käytä myös tarkistamattomat esimerkit")
def train(base_model, epochs, batch_size, lora_rank, learning_rate,
          export_ollama, kaikki):
    """
    Treeni paikallinen kielimalli laiteluettelo-purkuun.

    Suositukset:
      - Vähintään 10 tarkistettua esimerkkiä ennen fine-tuningia
      - GPU (CUDA) nopeuttaa merkittävästi mutta ei pakollinen
      - Phi-3.5-mini (3.8B) toimii hyvin 16GB RAM:lla ilman GPU:ta
    """
    # Tarkista dataset
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.dataset_builder import get_dataset_stats, export_as_jsonl

    stats = get_dataset_stats()
    console.print(Panel(
        f"Dataset: {stats['total']} esimerkkiä "
        f"({stats['verified']} tarkistettu)\n"
        f"Pohjamodel: {base_model}\n"
        f"Epookit: {epochs}, Batch: {batch_size}, LoRA rank: {lora_rank}",
        title="Fine-tuning asetukset",
    ))

    min_verified = 5
    if stats["verified"] < min_verified and not kaikki:
        console.print(
            f"[yellow]Varoitus: vain {stats['verified']} tarkistettua esimerkkiä "
            f"(suositus: {min_verified}+).[/yellow]\n"
            f"Käytä --kaikki tai tarkista lisää esimerkkejä ensin."
        )
        if stats["verified"] == 0:
            console.print("[red]Ei yhtään tarkistettua esimerkkiä. Abortataan.[/red]")
            return

    # Vie dataset
    jsonl_path = export_as_jsonl(verified_only=not kaikki)
    if not jsonl_path.exists() or jsonl_path.stat().st_size == 0:
        console.print("[red]Dataset on tyhjä. Kerää enemmän esimerkkejä.[/red]")
        return

    # Lataa Unsloth
    console.print("\n[dim]Ladataan Unsloth...[/dim]")
    try:
        from unsloth import FastLanguageModel
        from unsloth.chat_templates import get_chat_template
        import torch
    except ImportError:
        console.print(Panel(
            "[red bold]Unsloth ei ole asennettu![/red bold]\n\n"
            "Asenna komennolla:\n"
            "  [yellow]pip install unsloth[/yellow]\n\n"
            "GPU (CUDA) -tuki:\n"
            "  [yellow]pip install torch --index-url https://download.pytorch.org/whl/cu121[/yellow]",
            title="Virhe", border_style="red",
        ))
        return

    # Lataa malli LoRA-adaptrilla
    console.print(f"Ladataan pohjamallia: [cyan]{base_model}[/cyan]")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=4096,
        load_in_4bit=True,  # 4-bit kvantisointi — säästää muistia
        dtype=None,         # Auto-detect
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_rank,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=lora_rank,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Chat-template
    tokenizer = get_chat_template(tokenizer, chat_template="chatml")

    # Lataa ja formatoi data
    examples = load_dataset(jsonl_path, verified_only=not kaikki)
    formatted = format_for_training(examples)

    console.print(f"Treenidata: {len(formatted)} esimerkkiä")

    # Treenaa
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import Dataset

    dataset = Dataset.from_list(formatted)

    def formatting_func(example):
        text = tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )
        return {"text": text}

    dataset = dataset.map(formatting_func, remove_columns=["messages"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=4096,
        dataset_num_proc=1,
        args=TrainingArguments(
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=max(1, 4 // batch_size),
            warmup_steps=5,
            num_train_epochs=epochs,
            learning_rate=learning_rate,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            output_dir=str(OUTPUT_DIR),
            save_strategy="epoch",
        ),
    )

    console.print(f"\n[bold green]Aloitetaan treeniä...[/bold green]")
    trainer_stats = trainer.train()
    console.print(f"\n[green]Treeni valmis![/green]")
    console.print(f"  Aika: {trainer_stats.metrics.get('train_runtime', 0):.0f}s")
    console.print(f"  Loss: {trainer_stats.metrics.get('train_loss', 0):.4f}")

    # Tallenna LoRA-adapteri
    lora_path = OUTPUT_DIR / "lora_adapter"
    model.save_pretrained(str(lora_path))
    tokenizer.save_pretrained(str(lora_path))
    console.print(f"\n[green]LoRA-adapteri tallennettu:[/green] {lora_path}")

    # Vie Ollama-mallina
    if export_ollama:
        _export_to_ollama(model, tokenizer, base_model)


def _export_to_ollama(model, tokenizer, base_model: str):
    """Vie fine-tunattu malli Ollama-formaattiin."""
    import subprocess

    merged_path = OUTPUT_DIR / "merged_model"
    console.print(f"\n[dim]Yhdistetään LoRA base-malliin...[/dim]")

    model.save_pretrained_merged(
        str(merged_path),
        tokenizer,
        save_method="merged_16bit",
    )

    # Luo GGUF (Ollama-formaatti)
    gguf_path = OUTPUT_DIR / "laiteluettelo_model.gguf"
    console.print("[dim]Muunnetaan GGUF-formaattiin...[/dim]")
    model.save_pretrained_gguf(
        str(OUTPUT_DIR / "laiteluettelo_model"),
        tokenizer,
        quantization_method="q4_k_m",  # Hyvä laatu/koko-kompromissi
    )

    # Luo Modelfile Ollamalle
    modelfile_content = f"""FROM {OUTPUT_DIR}/laiteluettelo_model-unsloth.Q4_K_M.gguf

SYSTEM \"\"\"{SYSTEM_PROMPT}\"\"\"

PARAMETER temperature 0.0
PARAMETER num_predict 4096
"""

    modelfile_path = OUTPUT_DIR / "Modelfile"
    modelfile_path.write_text(modelfile_content)

    # Rekisteröi Ollamaan
    model_name = "laiteluettelo"
    result = subprocess.run(
        ["ollama", "create", model_name, "-f", str(modelfile_path)],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        console.print(Panel(
            f"[green bold]Malli rekisteröity Ollamaan![/green bold]\n\n"
            f"Käytä nyt:\n"
            f"  [yellow]python main.py purku TK01.pdf --model {model_name}[/yellow]",
            title="Valmis",
        ))
    else:
        console.print(f"[red]Ollama-rekisteröinti epäonnistui:[/red] {result.stderr}")
        console.print(f"Voit rekisteröidä manuaalisesti:\n"
                      f"  ollama create laiteluettelo -f {modelfile_path}")


if __name__ == "__main__":
    train()
