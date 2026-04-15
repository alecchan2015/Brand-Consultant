"""
AI Logo / Image Generation Service
Supports: OpenAI (DALL-E 3), Volcano Engine (豆包视觉), Stability AI
Reuses LLMConfig with agent_type="image_gen".
"""
import io
import re
import httpx
from typing import Optional

try:
    from PIL import Image
except ImportError:
    Image = None


def _build_logo_prompt(brand_name: str, content: str) -> str:
    """Extract style cues from brand content and build an image generation prompt."""
    # Extract color codes
    hex_colors = re.findall(r'#([A-Fa-f0-9]{6})', content)
    color_desc = ""
    if hex_colors:
        color_desc = f"using brand colors #{hex_colors[0]} and #{hex_colors[1]}" if len(hex_colors) >= 2 \
            else f"using brand color #{hex_colors[0]}"

    # Extract style keywords
    style_hints = []
    if any(w in content for w in ["高端", "奢华", "luxury", "premium"]):
        style_hints.append("luxury premium style")
    if any(w in content for w in ["简约", "极简", "minimal", "clean"]):
        style_hints.append("minimalist clean design")
    if any(w in content for w in ["科技", "智能", "tech", "smart", "IoT"]):
        style_hints.append("modern tech-forward")
    if any(w in content for w in ["自然", "生态", "natural", "organic"]):
        style_hints.append("organic natural feel")
    if any(w in content for w in ["家具", "窗", "门", "室内", "furniture", "interior"]):
        style_hints.append("interior design home decor")
    style_str = ", ".join(style_hints) if style_hints else "modern professional"

    prompt = (
        f"A professional brand logo for '{brand_name}', {style_str}, {color_desc}. "
        "Clean vector-style flat design, white background, centered composition, "
        "suitable for a brand identity system. No text, no watermark, no border. "
        "High quality, crisp edges, corporate aesthetic."
    )
    return prompt


async def _download_image(url: str) -> Optional["Image.Image"]:
    """Download image from URL and return as PIL Image."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")


async def _generate_via_openai_compat(config, prompt: str) -> Optional["Image.Image"]:
    """Works for OpenAI DALL-E 3 and Volcano Engine (both use OpenAI-compatible API)."""
    from openai import AsyncOpenAI

    kwargs = {"api_key": config.api_key}
    if config.base_url:
        kwargs["base_url"] = config.base_url

    client = AsyncOpenAI(**kwargs)

    try:
        response = await client.images.generate(
            model=config.model_name,
            prompt=prompt,
            n=1,
            size="1024x1024",
        )
        image_url = response.data[0].url
        if image_url:
            return await _download_image(image_url)

        # Some providers return b64_json instead of url
        b64 = response.data[0].b64_json
        if b64:
            import base64
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")

    except Exception as e:
        print(f"[image_service] OpenAI-compat generation failed: {e}")
    return None


async def _generate_via_stability(config, prompt: str) -> Optional["Image.Image"]:
    """Stability AI REST API (api.stability.ai)."""
    base = config.base_url or "https://api.stability.ai"
    engine = config.model_name or "stable-diffusion-xl-1024-v1-0"
    url = f"{base}/v1/generation/{engine}/text-to-image"

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {
        "text_prompts": [{"text": prompt, "weight": 1.0}],
        "cfg_scale": 7,
        "height": 1024,
        "width": 1024,
        "samples": 1,
        "steps": 30,
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            import base64
            b64 = data["artifacts"][0]["base64"]
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    except Exception as e:
        print(f"[image_service] Stability generation failed: {e}")
    return None


async def generate_logo_image(
    brand_name: str,
    content: str,
    db,
) -> Optional["Image.Image"]:
    """
    Main entry point. Looks up active image_gen LLMConfig and calls the
    appropriate provider. Returns a PIL RGBA Image or None if unconfigured/failed.
    """
    if Image is None:
        return None

    from models import LLMConfig
    config = (
        db.query(LLMConfig)
        .filter(LLMConfig.agent_type == "image_gen", LLMConfig.is_active == True)
        .first()
    )
    if not config:
        print("[image_service] No active image_gen config found, skipping logo generation.")
        return None

    prompt = _build_logo_prompt(brand_name, content)
    print(f"[image_service] Generating logo with provider={config.provider} model={config.model_name}")
    print(f"[image_service] Prompt: {prompt}")

    if config.provider in ("openai", "volcano"):
        return await _generate_via_openai_compat(config, prompt)
    elif config.provider == "stability":
        return await _generate_via_stability(config, prompt)
    else:
        print(f"[image_service] Unknown provider: {config.provider}")
        return None
