# Fine-tune Laiteluettelo Model in Google Colab

## Setup Instructions

### 1. Go to Google Colab
Open https://colab.research.google.com

### 2. Create New Notebook
Click **File → New notebook**

### 3. Copy-paste the code below into the first cell:

```python
# Install dependencies
!pip install -q unsloth[colab-new] xformers datasets trl peft

# Download your training data
!mkdir -p laiteluettelo_colab
%cd laiteluettelo_colab

# Clone the repo (or upload files manually)
!git clone https://github.com/anttip1197/laiteluettelo.git --depth 1
%cd laiteluettelo

print("✓ Dependencies installed!")
```

Run the cell (Ctrl+Enter)

---

### 4. Copy-paste this cell for TRAINING DATA:

If you want to **upload your own dataset** instead of using git:

```python
from google.colab import files
import json

# Upload your dataset.jsonl file
print("Upload your training/dataset.jsonl file:")
uploaded = files.upload()

# Save it
for filename, file_data in uploaded.items():
    with open(f"training/{filename}", "wb") as f:
        f.write(file_data)
    print(f"✓ Saved {filename}")
```

---

### 5. Copy-paste this cell to RUN FINE-TUNING:

```python
import json
from pathlib import Path
from datasets import Dataset
from unsloth import FastLanguageModel
from transformers import TrainingArguments
from trl import SFTTrainer

# Load training data
DATASET_PATH = Path("training/dataset.jsonl")
examples = []

with open(DATASET_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            examples.append(json.loads(line))

print(f"✓ Loaded {len(examples)} training examples")

# Format as chat
def format_chat_example(example):
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

formatted = [format_chat_example(ex) for ex in examples]
dataset = Dataset.from_dict({
    "messages": [ex["messages"] for ex in formatted]
})

print("✓ Formatted training data")

# Load model
print("Loading Phi-3.5-mini...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Phi-3.5-mini-instruct",
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

print("✓ Model loaded with LoRA")

# Training
training_args = TrainingArguments(
    output_dir="output/checkpoint",
    num_train_epochs=3,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    warmup_steps=2,
    learning_rate=2e-4,
    fp16=True,
    logging_steps=1,
    optim="adamw_8bit",
    seed=42,
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    args=training_args,
    train_dataset=dataset,
    dataset_text_field="messages",
    packing=False,
    max_seq_length=4096,
)

print("Starting training...")
trainer.train()
print("✓ Training complete!")

# Save
model.save_pretrained("output/laiteluettelo_ft")
tokenizer.save_pretrained("output/laiteluettelo_ft")
print("✓ Model saved to output/laiteluettelo_ft")

# Merge
model = FastLanguageModel.for_inference(model)
model.save_pretrained("output/laiteluettelo_merged")
tokenizer.save_pretrained("output/laiteluettelo_merged")
print("✓ Merged model saved to output/laiteluettelo_merged")
```

Run the cell - fine-tuning will start!

---

### 6. Copy-paste this cell to DOWNLOAD the model:

```python
from google.colab import files
import shutil

# Zip the model
shutil.make_archive("laiteluettelo_merged", "zip", "output", "laiteluettelo_merged")

# Download
files.download("laiteluettelo_merged.zip")
print("✓ Download started!")
```

---

## After Colab: Use the Model Locally

### 1. Extract the downloaded zip file:
```bash
unzip laiteluettelo_merged.zip
```

### 2. Move to your project:
```bash
mv laiteluettelo_merged c:\Users\anttipar\laiteluettelo\training\model_output\
```

### 3. Create Modelfile for Ollama:

**Option A - Windows (PowerShell):**
```powershell
cd c:\Users\anttipar\laiteluettelo\training\model_output
@"
FROM laiteluettelo_merged
SYSTEM "You are an expert HVAC engineering assistant. Extract structured technical data and return ONLY valid JSON."
"@ | Out-File -Encoding utf8 Modelfile
```

**Option B - Windows (Bash/MINGW):**
```bash
cd c:/Users/anttipar/laiteluettelo/training/model_output
echo FROM laiteluettelo_merged > Modelfile
echo 'SYSTEM "You are an expert HVAC engineering assistant. Extract structured technical data and return ONLY valid JSON."' >> Modelfile
```

**Option C - Manual:**
1. Create file `c:\Users\anttipar\laiteluettelo\training\model_output\Modelfile` (no extension)
2. Add these 2 lines:
```
FROM laiteluettelo_merged
SYSTEM "You are an expert HVAC engineering assistant. Extract structured technical data and return ONLY valid JSON."
```

### 4. Import to Ollama:
```bash
cd c:\Users\anttipar\laiteluettelo\training\model_output
ollama create laiteluettelo-custom -f Modelfile
```

### 5. Test with main.py:
```bash
python main.py koneajo/TK01.pdf --model laiteluettelo-custom
```

---

## Tips

- **Upload more examples** before training for better results (5-10 examples recommended)
- Colab session times out after 30 min of inactivity - save model before that
- Training should take 2-5 minutes on GPU
- You can run multiple trainings with different base models (Mistral 7B, Qwen2.5, etc.)

