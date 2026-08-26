# Phase 9A — GeoChat-7B local smoke test (TEMPORARY, not part of SatQuery-AI)

This folder is a throwaway research artifact for Phase 9A model-setup verification.
It is **not imported by `backend/` or `frontend/`** and is git-ignored except for this
README and the scripts below.

## Result

Local fp16 inference on this machine (MacBook Air, Apple M5, 16GB unified memory)
failed safely: the memory watchdog killed the loading process before the OS ran low
on available memory. See the chat transcript / final report for full analysis.

**Decision: Cloud inference required (option C).** No production code was touched.

## Files
- `fetch_image.py` — pulls one real Sentinel-2 RGB thumbnail via the already-authenticated
  Earth Engine credentials on this machine (B04/B03/B02 → RGB, true-color stretch).
- `smoke_test_worker.py` — loads GeoChat-7B (`MBZUAI/geochat-7B`) and runs one VQA + one
  grounding prompt.
- `watchdog.py` — runs the worker as a subprocess and kills it if memory usage becomes
  unsafe, so the smoke test can never freeze the host machine.
- `GeoChat_src/` (git-ignored) — shallow clone of `mbzuai-oryx/GeoChat` for the custom
  `GeoChatLlamaForCausalLM` model class. One line patched (`geochat/model/__init__.py`)
  to make the unused MPT variant import optional (incompatible with modern `transformers`
  and irrelevant to the LLaMA/Vicuna-based `geochat-7B` checkpoint we use).
- `.venv/` (git-ignored) — isolated Python 3.11 venv, separate from `backend/.venv`.

## Safe to delete
This entire folder (and `~/.cache/huggingface/hub/models--MBZUAI--geochat-7B` /
`models--openai--clip-vit-large-patch14-336`, ~14.6GB) can be deleted at any time
without affecting SatQuery-AI.
