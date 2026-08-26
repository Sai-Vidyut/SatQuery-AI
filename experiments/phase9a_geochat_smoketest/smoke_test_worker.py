"""
PHASE 9A SMOKE TEST — WORKER (temporary script, not part of SatQuery-AI).

Loads GeoChat-7B and runs ONE genuine VQA inference on a real Sentinel-2
RGB image. Designed to be launched by watchdog.py, which kills this
process if memory usage approaches an unsafe limit.

Writes progress lines to stdout (flushed) so the watchdog / operator can
follow along, and writes the final answer to result.json.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent


def log(msg):
    print(f"[worker] {msg}", flush=True)


def main():
    t_start = time.time()
    log("importing torch/transformers...")
    import torch
    from transformers import AutoTokenizer

    sys.path.insert(0, str(HERE / "GeoChat_src"))
    from geochat.model.language_model.geochat_llama import GeoChatLlamaForCausalLM
    from geochat.mm_utils import process_images_demo, tokenizer_image_token
    from geochat.constants import IMAGE_TOKEN_INDEX

    model_path = "MBZUAI/geochat-7B"

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    log(f"target device: {device}")

    log("loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)

    log("loading GeoChatLlamaForCausalLM weights (fp16, low_cpu_mem_usage) ... this is the ~14GB step")
    t_load_start = time.time()
    model = GeoChatLlamaForCausalLM.from_pretrained(
        model_path,
        low_cpu_mem_usage=True,
        torch_dtype=torch.float16,
    )
    load_s = time.time() - t_load_start
    log(f"base weights loaded in {load_s:.1f}s")

    log("loading CLIP vision tower (openai/clip-vit-large-patch14-336)...")
    vision_tower = model.get_vision_tower()
    if not vision_tower.is_loaded:
        vision_tower.load_model()
    vision_tower.to(dtype=torch.float16)
    image_processor = vision_tower.image_processor
    log("vision tower ready")

    log(f"moving full model to device={device} (fp16)...")
    t_move = time.time()
    model.to(device)
    model.eval()
    log(f"moved to {device} in {time.time() - t_move:.1f}s")

    total_load_s = time.time() - t_start
    log(f"TOTAL LOAD TIME: {total_load_s:.1f}s")

    # ---- VQA smoke test ----
    from PIL import Image

    image_path = HERE / "smoketest_image.png"
    raw_image = Image.open(image_path).convert("RGB")
    image_tensor = process_images_demo([raw_image], image_processor)
    image_tensor = image_tensor.to(device=device, dtype=torch.float16)

    question = "What type of land cover is visible in this image?"
    prompt = (
        "A chat between a curious user and an artificial intelligence assistant. "
        "The assistant gives helpful, detailed, and polite answers to the user's questions. "
        f"USER: <image>\n{question} ASSISTANT:"
    )

    input_ids = tokenizer_image_token(
        prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
    ).unsqueeze(0).to(device)

    log("running generate() for VQA question...")
    t_gen = time.time()
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids,
            images=image_tensor,
            do_sample=False,
            temperature=1.0,
            max_new_tokens=200,
            use_cache=True,
        )
    gen_s = time.time() - t_gen
    answer = tokenizer.decode(
        output_ids[0, input_ids.shape[1]:], skip_special_tokens=True
    ).strip()
    log(f"VQA generation took {gen_s:.1f}s")
    log(f"ANSWER: {answer}")

    result = {
        "device": device,
        "load_time_s": total_load_s,
        "vqa_question": question,
        "vqa_answer": answer,
        "vqa_generation_time_s": gen_s,
    }

    # ---- Grounding smoke test (only if VQA succeeded) ----
    grounding_question = "[identify] {<p>the field boundaries near the village</p>}"
    try:
        log("attempting grounding smoke test...")
        prompt_g = (
            "A chat between a curious user and an artificial intelligence assistant. "
            "The assistant gives helpful, detailed, and polite answers to the user's questions. "
            f"USER: <image>\nDetect the settlement or built-up area in this image and provide its "
            f"bounding box. ASSISTANT:"
        )
        input_ids_g = tokenizer_image_token(
            prompt_g, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
        ).unsqueeze(0).to(device)
        t_g = time.time()
        with torch.inference_mode():
            output_ids_g = model.generate(
                input_ids_g,
                images=image_tensor,
                do_sample=False,
                temperature=1.0,
                max_new_tokens=200,
                use_cache=True,
            )
        g_s = time.time() - t_g
        grounding_answer = tokenizer.decode(
            output_ids_g[0, input_ids_g.shape[1]:], skip_special_tokens=True
        ).strip()
        log(f"GROUNDING ANSWER: {grounding_answer}")
        result["grounding_prompt"] = prompt_g
        result["grounding_answer"] = grounding_answer
        result["grounding_generation_time_s"] = g_s
    except Exception as e:
        log(f"grounding smoke test failed: {e}")
        result["grounding_error"] = str(e)

    (HERE / "result.json").write_text(json.dumps(result, indent=2))
    log("wrote result.json")


if __name__ == "__main__":
    main()
