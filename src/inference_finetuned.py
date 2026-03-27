"""
Use fine-tuned model for inference without Ollama.
Works directly with HuggingFace model files.
"""
import json
from pathlib import Path
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# Path to fine-tuned model
MODEL_PATH = Path(__file__).parent.parent / "training" / "model_output" / "laiteluettelo_merged"


def load_finetuned_model():
    """Load the fine-tuned model and tokenizer."""
    print(f"Loading fine-tuned model from {MODEL_PATH}...")

    # Check if model exists
    if not MODEL_PATH.exists():
        raise RuntimeError(f"Model not found at {MODEL_PATH}")

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH))

    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_PATH),
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )

    return model, tokenizer


def extract_with_finetuned(pdf_text: str, model=None, tokenizer=None) -> Optional[dict]:
    """
    Extract equipment data using fine-tuned model.
    If model/tokenizer not provided, loads them.
    """
    if model is None or tokenizer is None:
        model, tokenizer = load_finetuned_model()

    # Create prompt
    system_prompt = """You are an expert HVAC engineering assistant specializing in Finnish ventilation systems.
Your task: extract structured technical data from ventilation unit specification sheets and return ONLY valid JSON.
IMPORTANT: Return ONLY valid JSON. No explanations, no markdown, no code blocks. Pure JSON only.
REQUIRED: type field must be one of: SP, FG, SU, LTO, TF, LP, JP, AV, HPE, HPO, SOUND"""

    # Truncate if too long
    max_chars = 8000
    if len(pdf_text) > max_chars:
        pdf_text = pdf_text[:max_chars] + "\n...[truncated]"

    user_message = f"""Extract all components from this ventilation unit specification:

{pdf_text}

Return valid JSON only."""

    # Format as chat
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # Tokenize
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)

    # Generate
    print("Generating extraction...")
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_new_tokens=2048,
            temperature=0.1,
            top_p=0.9,
            do_sample=True,
        )

    # Decode
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Extract JSON from response
    try:
        # Find JSON in response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from response: {response[:200]}")

    return None


if __name__ == "__main__":
    # Test
    print("Fine-tuned model inference ready!")
    print(f"Model location: {MODEL_PATH}")
    print("Use: from src.inference_finetuned import extract_with_finetuned")
