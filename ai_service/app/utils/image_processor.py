import base64
import io
from typing import List, Tuple

from loguru import logger
from PIL import Image

# Default settings for image compression
DEFAULT_MAX_SIZE = 1024  # Max dimension (px) on the longest side
DEFAULT_QUALITY = 75  # JPEG quality (1-100)


def compress_image(
    b64_input: str,
    max_size: int = DEFAULT_MAX_SIZE,
    quality: int = DEFAULT_QUALITY,
) -> Tuple[str, str]:
    """Compress a base64-encoded image to reduce token costs.

    Args:
        b64_input: Base64 string, optionally with data:image/...;base64, prefix
        max_size: Maximum dimension in pixels (longest side)
        quality: JPEG compression quality (1-100)

    Returns:
        Tuple of (compressed_base64_string, mime_type)
        Returns original if compression fails.
    """
    mime_type = "image/jpeg"
    clean_b64 = b64_input

    try:
        # Strip data URI prefix if present
        if b64_input.startswith("data:"):
            header, clean_b64 = b64_input.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]

        # Decode base64 to bytes
        original_bytes = base64.b64decode(clean_b64, validate=True)
        original_size = len(original_bytes)

        # Open with Pillow
        img = Image.open(io.BytesIO(original_bytes))

        # Convert RGBA/P to RGB for JPEG compatibility
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # Only resize if larger than max_size (avoid upscaling)
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Compress to JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = buffer.getvalue()
        compressed_size = len(compressed_bytes)

        # Encode back to base64
        compressed_b64 = base64.b64encode(compressed_bytes).decode("utf-8")

        logger.info(
            f"Image compressed: {original_size / 1024:.1f}KB → {compressed_size / 1024:.1f}KB "
            f"({img.size[0]}x{img.size[1]}px, quality={quality})"
        )

        return compressed_b64, "image/jpeg"

    except Exception as e:
        logger.error(f"Failed to compress image, using original. Error: {e}")
        # Return original (stripped of prefix) if compression fails
        return clean_b64, mime_type


def process_images(
    images: List[str],
    max_size: int = DEFAULT_MAX_SIZE,
    quality: int = DEFAULT_QUALITY,
) -> List[str]:
    """Compress a list of base64 images for LLM consumption.

    Args:
        images: List of base64 strings (with or without data URI prefix)
        max_size: Maximum dimension in pixels
        quality: JPEG quality

    Returns:
        List of compressed base64 strings with data URI prefix (ready for LLM)
    """
    if not images:
        return []

    processed = []
    for i, img_b64 in enumerate(images):
        if not img_b64 or not img_b64.strip():
            continue

        compressed_b64, mime_type = compress_image(img_b64, max_size, quality)

        # Return with data URI prefix for consistency
        processed.append(f"data:{mime_type};base64,{compressed_b64}")

    logger.info(f"Processed {len(processed)}/{len(images)} images")
    return processed
