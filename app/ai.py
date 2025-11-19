import asyncio
import base64
import io
import json
import logging

from litellm import acompletion
from PIL import Image

from . import models

# Default configuration (can be overridden by DB settings)
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "moondream"
DEFAULT_API_BASE = "http://ollama:11434"

logger = logging.getLogger(__name__)

def _process_image(image_path):
    """
    Synchronous image processing function to be run in an executor.
    """
    try:
        with Image.open(image_path) as img:
            # Resize if too large (e.g., max dimension 1024)
            max_size = 1024
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size))
                logger.info(f"Resized image to {img.size}")

            # Convert to RGB if necessary (e.g. for PNGs with alpha)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        raise

async def encode_image(image_path):
    """
    Asynchronously encode image by running blocking code in a thread.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _process_image, image_path)

def clean_text(text: str) -> str:
    """
    Cleans the text by removing code blocks, HTML tags, and excessive whitespace.
    """
    import re
    if not text:
        return ""

    # Remove code blocks (```...```)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)

    # Remove HTML tags (basic)
    text = re.sub(r'<[^>]+>', '', text)

    # Remove non-printable characters (keep newlines and tabs)
    text = re.sub(r'[^\x20-\x7E\n\t]', '', text)

    # Collapse excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def get_ai_config():
    """
    Fetches AI configuration from the database.
    Returns a tuple: (provider, model, api_key, api_base)
    """
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        settings = session.query(models.Settings).all()
        settings_map = {s.key: s.value for s in settings}

        provider = settings_map.get("ai_provider", DEFAULT_PROVIDER)
        model = settings_map.get("ai_model", DEFAULT_MODEL)
        api_key = settings_map.get("ai_api_key", "")
        api_base = settings_map.get("ai_api_base", DEFAULT_API_BASE)

        return provider, model, api_key, api_base
    except Exception as e:
        logger.error(f"Error fetching AI config: {e}")
        return DEFAULT_PROVIDER, DEFAULT_MODEL, "", DEFAULT_API_BASE
    finally:
        session.close()

async def analyze_image(image_path: str, page_text: str = "", prompt: str = "What is the price of the product in this image? If it is out of stock, say 'Out of Stock'; but if it shows Add to Cart or something similar say In Stock. Return a JSON object with keys 'price' (number or null) and 'in_stock' (boolean)."):
    try:
        # Note: get_ai_config is sync but fast (DB read), could be async if needed but acceptable for now
        # or we could wrap it. For now, let's leave it as is or wrap it if we want to be strict.
        # Given it creates a session, it's blocking. Let's wrap it.
        loop = asyncio.get_running_loop()
        provider, model, api_key, api_base = await loop.run_in_executor(None, get_ai_config)

        logger.info(f"Analyzing image with Provider: {provider}, Model: {model}")

        base64_image = await encode_image(image_path)
        data_url = f"data:image/jpeg;base64,{base64_image}"

        final_prompt = prompt
        if page_text:
            cleaned_text = clean_text(page_text)
            # Truncate text if too long to avoid token limits (rough estimate)
            if len(cleaned_text) > 10000:
                cleaned_text = cleaned_text[:10000] + "...(truncated)"
            final_prompt = f"{prompt}\n\nContext from webpage text:\n{cleaned_text}"
            logger.info(f"Added text context to prompt (original: {len(page_text)}, cleaned: {len(cleaned_text)})")

        # Construct messages for litellm
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": final_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ]

        # Prepare kwargs for litellm
        kwargs = {
            "model": model if provider != "ollama" else f"ollama/{model}",
            "messages": messages,
            "max_tokens": 300,
        }

        if api_key:
            kwargs["api_key"] = api_key

        if provider == "ollama":
            kwargs["api_base"] = api_base
            kwargs["format"] = "json" # Force JSON mode for Ollama
        elif provider == "openai" and api_base:
             # Allow custom base URL for OpenAI-compatible endpoints too
             kwargs["api_base"] = api_base

        # Call litellm asynchronously
        logger.info(f"Sending request to {provider} ({model})...")
        response = await acompletion(**kwargs)

        response_text = response.choices[0].message.content
        logger.info(f"AI Response: {response_text}")

        # Parse JSON
        try:
            # Try to find JSON block
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
            else:
                data = json.loads(response_text)

            # Clean price
            if "price" in data:
                if isinstance(data["price"], str):
                    price_match = re.search(r'(\d+\.?\d*)', data["price"])
                    if price_match:
                        data["price"] = float(price_match.group(1))
                    else:
                        data["price"] = None
                elif isinstance(data["price"], (int, float)):
                    data["price"] = float(data["price"])

            return data

        except (json.JSONDecodeError, ValueError):
            # Fallback parsing
            logger.warning("Failed to parse JSON, attempting fallback parsing")
            # Look for price with $ symbol first
            price_match = re.search(r'\$\s?(\d+(?:\.\d{1,2})?)', response_text)
            if not price_match:
                # If no $ found, look for "price is X" pattern
                price_match = re.search(r'price\s+is\s+(\d+(?:\.\d{1,2})?)', response_text, re.IGNORECASE)

            price = float(price_match.group(1)) if price_match else None
            in_stock = "out of stock" not in response_text.lower()
            return {"price": price, "in_stock": in_stock}

    except Exception as e:
        logger.error(f"Error calling AI provider: {e}", exc_info=True)
        return None
