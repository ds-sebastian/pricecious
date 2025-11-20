import asyncio
import base64
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

# Image processing constants
MAX_IMAGE_SIZE = 1024
JPEG_QUALITY = 85


def _process_image(image_path: str) -> str:
    """
    Synchronous image processing function to be run in an executor.
    """
    try:
        with Image.open(image_path) as img:
            # Resize if too large (e.g., max dimension 1024)
            if max(img.size) > MAX_IMAGE_SIZE:
                img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))
                logger.info(f"Resized image to {img.size}")

            # Convert to RGB if necessary (e.g. for PNGs with alpha)
            if img.mode in ("RGBA", "P"):
                img_to_process = img.convert("RGB")
            else:
                img_to_process = img

            buffered = io.BytesIO()
            img_to_process.save(buffered, format="JPEG", quality=JPEG_QUALITY)
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        raise


async def encode_image(image_path: str) -> str:
    """
    Asynchronously encode image by running blocking code in a thread.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _process_image, image_path)
