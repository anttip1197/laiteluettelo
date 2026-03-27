#!/usr/bin/env python3
"""
Fine-tune a model on laiteluettelo extraction task using Unsloth.
Creates a custom model optimized for Finnish HVAC equipment extraction.

Usage:
  python training/fine_tune_laiteluettelo.py
  python training/fine_tune_laiteluettelo.py --base-model unsloth/mistral-7b-instruct-v0.3
  python training/fine_tune_laiteluettelo.py --epochs 5 --lr 1e-4
"""
import json
from pathlib import Path
from datasets import Dataset

import click
from rich.console import Console
from rich.panel import Panel

console = Console()

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
OUTPUT_DIR = Path(__file__).parent / "model_output"

OUTPUT_DIR.mkdir(exist_ok=True)


def load_training_examples(path: Path) -> list[dict]:
    """Load training examples from JSONL."""
    examples = []
    if not path.exists():
        console.print(f"[red]Error: {path} not found[/red]")
        return []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def format_chat_example(example: dict) -> dict:
    """Format example as chat messages."""
    input_text = example["input"]
    output_json = json.dumps(example["output"], ensure_ascii=False)

    messages = [
        {
            "role": "user",
            "content": f"Extract structured technical data from this ventilation specification:\n\n{input_text}"
        },
        {
            "role": "assistant",
            "content": output_json
        }
    ]

    return {"messages": messages}


@click.command()
@click.option(
    "--base-model",
    default="unsloth/Phi-3.5-mini-instruct",
    help="Base model (phi3.5, mistral-7b, llama3.2, qwen2.5)"
)
@click.option("--epochs", default=3, type=int, help="Training epochs")
@click.option("--batch-size", default=1, type=int, help="Batch size")
@click.option("--lr", default=2e-4, type=float, help="Learning rate")
@click.option("--export-gguf", is_flag=True, help="Export to GGUF format")
def fine_tune(base_model: str, epochs: int, batch_size: int, lr: float, export_gguf: bool):
    """Fine-tune a model on laiteluettelo data using Unsloth + LoRA."""

    console.print(Panel("LVI Laiteluettelo Fine-tuning", title="Fine-Tune"))

    # Load training data
    examples = load_training_examples(DATASET_PATH)
    if not examples:
        console.print("[red]No training examples found at {DATASET_PATH}[/red]")
        return

    console.print(f"[cyan]Loaded {len(examples)} training examples[/cyan]")

    # Import dependencies
    try:
        from unsloth import FastLanguageModel
        from transformers import TrainingArguments
        from trl import SFTTrainer
    except ImportError:
        console.print("[red]Dependencies not installed![/red]")
        console.print("[yellow]Run: pip install unsloth[colab-new] xformers datasets[/yellow]")
        return

    # Load model
    console.print(f"[cyan]Loading {base_model}...[/cyan]")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=4096,
        dtype="auto",
        load_in_4bit=True,
    )

    # Add LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Prepare dataset
    console.print("[cyan]Formatting training data...[/cyan]")
    formatted = [format_chat_example(ex) for ex in examples]
    dataset = Dataset.from_dict({
        "messages": [ex["messages"] for ex in formatted]
    })

    # Training config
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR / "checkpoint"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        warmup_steps=2,
        learning_rate=lr,
        fp16=True,
        logging_steps=1,
        optim="adamw_8bit",
        seed=42,
    )

    # Train
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        train_dataset=dataset,
        dataset_text_field="messages",
        packing=False,
        max_seq_length=4096,
    )

    console.print("[cyan]Starting training...[/cyan]")
    trainer.train()

    # Save
    console.print("[cyan]Saving fine-tuned model...[/cyan]")
    model.save_pretrained(OUTPUT_DIR / "laiteluettelo_ft")
    tokenizer.save_pretrained(OUTPUT_DIR / "laiteluettelo_ft")

    console.print(f"[green]✓ Fine-tuned model saved to {OUTPUT_DIR / 'laiteluettelo_ft'}[/green]")

    # Merge (optional)
    console.print("[cyan]Merging LoRA weights...[/cyan]")
    model = FastLanguageModel.for_inference(model)
    model.save_pretrained(OUTPUT_DIR / "laiteluettelo_merged")
    tokenizer.save_pretrained(OUTPUT_DIR / "laiteluettelo_merged")

    console.print(f"[green]✓ Merged model saved to {OUTPUT_DIR / 'laiteluettelo_merged'}[/green]")

    if export_gguf:
        console.print("[cyan]Converting to GGUF...[/cyan]")
        console.print("[yellow]This requires: pip install llama-cpp-python[/yellow]")


if __name__ == "__main__":
    fine_tune()
