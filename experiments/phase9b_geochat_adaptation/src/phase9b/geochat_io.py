"""GeoChat model input construction.

Pure construction logic that does NOT require torch/transformers to import
(so it is unit-testable on the Mac with no GPU). The actual tokenizer/image
processor objects are passed in by the caller (constructed in the cloud
smoke test script where transformers is actually installed), keeping this
module framework-light and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

IMAGE_TOKEN = "<image>"
IMAGE_TOKEN_INDEX = -200  # matches geochat/constants.py exactly


@dataclass(frozen=True)
class GeoChatPrompt:
    """A fully-assembled GeoChat prompt, ready for tokenization."""

    text: str
    image_path: Path


def build_vqa_prompt(
    *, system: str, question: str, image_path: Path, user_role: str = "USER", assistant_role: str = "ASSISTANT"
) -> GeoChatPrompt:
    """Build a single-turn VQA prompt matching GeoChat's conv_vicuna_v1 style
    (geochat/conversation.py), reproduced exactly (same separators/roles)
    rather than approximated.
    """
    if not question.strip():
        raise ValueError("question must not be empty")
    if not image_path.exists():
        raise FileNotFoundError(f"image_path does not exist: {image_path}")
    text = (
        f"{system.strip()} {user_role}: {IMAGE_TOKEN}\n{question.strip()} {assistant_role}:"
    )
    return GeoChatPrompt(text=text, image_path=image_path)


class TokenizerLike(Protocol):
    def __call__(self, text: str) -> Any: ...


def tokenizer_image_token(
    prompt: str, tokenizer: TokenizerLike, image_token_index: int = IMAGE_TOKEN_INDEX
) -> list[int]:
    """Reproduction of geochat/mm_utils.py:tokenizer_image_token.

    Splits the prompt on the literal `<image>` token and splices in a
    sentinel index (-200) wherever it occurred, exactly matching the
    upstream GeoChat tokenization contract (the model's forward pass
    expects this exact sentinel, not an actual vocabulary token).
    """
    chunks = [tokenizer(c).input_ids for c in prompt.split(IMAGE_TOKEN)]

    def insert_separator(seqs: list[list[int]], sep: list[int]) -> list[list[int]]:
        return [x for pair in zip(seqs, [sep] * len(seqs)) for x in pair][:-1]

    input_ids: list[int] = []
    offset = 0
    if chunks and chunks[0] and chunks[0][0] == tokenizer.bos_token_id:
        offset = 1
        input_ids.append(chunks[0][0])

    for x in insert_separator(chunks, [image_token_index] * (offset + 1)):
        input_ids.extend(x[offset:])
    return input_ids


def load_and_validate_image(image_path: Path, expected_px: int) -> Image.Image:
    """Load a preprocessed image and assert it matches the expected GeoChat
    input resolution (fails loudly rather than silently resizing again).
    """
    image = Image.open(image_path).convert("RGB")
    if image.size != (expected_px, expected_px):
        raise ValueError(
            f"{image_path} is {image.size}, expected ({expected_px}, {expected_px}). "
            "Run preprocessing.prepare_geochat_visual_input first."
        )
    return image
