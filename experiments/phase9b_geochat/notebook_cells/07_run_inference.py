# Cell 7 — one genuine GeoChat VQA inference on the Sentinel-2 image
import json
import time
from pathlib import Path

import torch
from PIL import Image

from geochat.constants import IMAGE_TOKEN_INDEX
from geochat.mm_utils import process_images_demo, tokenizer_image_token

config = json.loads(Path("/content/phase9b_geochat_smoke/smoke_config.json").read_text())
image_path = Path(config["image_path"])
question = config["question"]
prompt = f"{config['prompt_system']} USER: <image>\n{question} ASSISTANT:"

# Mixed CPU/GPU 8-bit models: place inputs on the first CUDA parameter device.
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
for p in model.parameters():
    if p.device.type == "cuda":
        device = p.device
        break
raw_image = Image.open(image_path).convert("RGB")
image_tensor = process_images_demo([raw_image], image_processor)
image_tensor = image_tensor.to(device=device, dtype=torch.float16)

input_ids = (
    tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt")
    .unsqueeze(0)
    .to(device)
)

print(f"Running GeoChat inference on device={device} ...")
t0 = time.time()
try:
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids,
            images=image_tensor,
            do_sample=False,
            temperature=1.0,
            max_new_tokens=200,
            use_cache=True,
        )
except torch.cuda.OutOfMemoryError as e:
    raise RuntimeError(f"CUDA OOM during inference: {e}") from e
except Exception as e:
    raise RuntimeError(f"inference failed: {e}") from e

gen_s = time.time() - t0
answer = tokenizer.decode(
    output_ids[0, input_ids.shape[1] :], skip_special_tokens=True
).strip()

if not answer:
    raise RuntimeError("Inference returned an empty answer.")

inference_report = {
    "question": question,
    "prompt": prompt,
    "answer": answer,
    "generation_time_s": round(gen_s, 2),
    "inference_device": str(device),
    "peak_vram_gb_after_inference": round(
        torch.cuda.max_memory_allocated() / (1024**3), 3
    ),
}
Path("/content/phase9b_geochat_smoke/inference_report.json").write_text(
    json.dumps(inference_report, indent=2)
)

print(f"Inference complete in {gen_s:.1f}s")
print("ANSWER:", answer)
