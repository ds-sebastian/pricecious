import requests
import base64
import os
import json
import logging
from PIL import Image
import io

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
if not OLLAMA_BASE_URL.startswith(("http://", "https://")):
    OLLAMA_BASE_URL = f"http://{OLLAMA_BASE_URL}"

MODEL_NAME = os.getenv("OLLAMA_MODEL", "moondream")

logger = logging.getLogger(__name__)

def encode_image(image_path):
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

def analyze_image(image_path: str, page_text: str = "", prompt: str = "What is the price of the product in this image? If it is out of stock, say 'Out of Stock'; but if it shows Add to Cart or something similar say In Stock. Return a JSON object with keys 'price' (number or null) and 'in_stock' (boolean)."):
    try:
        logger.info(f"Encoding image: {image_path}")
        base64_image = encode_image(image_path)
        
        final_prompt = prompt
        if page_text:
            cleaned_text = clean_text(page_text)
            final_prompt = f"{prompt}\n\nContext from webpage text:\n{cleaned_text}"
            logger.info(f"Added text context to prompt (original: {len(page_text)}, cleaned: {len(cleaned_text)})")

        payload = {
            "model": MODEL_NAME,
            "prompt": final_prompt,
            "images": [base64_image],
            "stream": False,
            "format": "json" 
        }
        
        logger.info(f"Sending request to Ollama at {OLLAMA_BASE_URL} with model {MODEL_NAME}")
        # Add timeout to prevent hanging indefinitely
        try:
            response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=120)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Model {MODEL_NAME} not found. Attempting to pull...")
                pull_payload = {"name": MODEL_NAME}
                # Pulling can take a long time, so we set a long timeout or stream it
                # For simplicity here, we'll just wait a bit, but ideally we should stream
                pull_response = requests.post(f"{OLLAMA_BASE_URL}/api/pull", json=pull_payload, stream=True)
                pull_response.raise_for_status()
                
                # Consume the stream to ensure it finishes
                for line in pull_response.iter_lines():
                    if line:
                        try:
                            status = json.loads(line).get("status")
                            if status:
                                logger.info(f"Pull status: {status}")
                        except:
                            pass
                
                logger.info(f"Model {MODEL_NAME} pulled successfully. Retrying generation...")
                response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=120)
                response.raise_for_status()
            else:
                raise e
        
        result = response.json()
        response_text = result.get("response", "")
        
        logger.info(f"Ollama response: {response_text}")
        
        # Attempt to parse JSON from the response
        try:
            data = json.loads(response_text)
            
            # Clean price if it's a string
            if "price" in data and isinstance(data["price"], str):
                try:
                    import re
                    # Extract number from string (e.g. "$99.95" -> 99.95)
                    price_match = re.search(r'(\d+\.?\d*)', data["price"])
                    if price_match:
                        data["price"] = float(price_match.group(1))
                    else:
                        data["price"] = None
                except ValueError:
                    data["price"] = None
            
            return data
        except json.JSONDecodeError:
            # Fallback parsing if model didn't return pure JSON
            import re
            price_match = re.search(r'\$?(\d+\.?\d*)', response_text)
            price = float(price_match.group(1)) if price_match else None
            in_stock = "out of stock" not in response_text.lower()
            return {"price": price, "in_stock": in_stock}

    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to Ollama")
        return None
    except Exception as e:
        logger.error(f"Error calling Ollama: {e}", exc_info=True)
        return None
