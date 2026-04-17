"""
Poster-image providers — dedicated provider chain for festival/event poster
backgrounds. Mirrors logo_providers but tuned for:
  - Portrait 9:16 by default (2160×3840)
  - Chinese-scene prompt hints baked in
  - Supports OpenAI-compatible endpoints (dall-e-3, gpt-image-1, 豆包/即梦 OpenAI-compat)
  - Supports Replicate-hosted FLUX (black-forest-labs/flux-1.1-pro)

Returns a list of (variant_index, url) dicts. Downstream compositor pulls
those URLs, composes them with logo/footer via Pillow, uploads to /uploads.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx


# ── Result ─────────────────────────────────────────────────────────────────
@dataclass
class PosterResult:
    success:  bool
    provider: str
    variants: List[Dict[str, Any]] = field(default_factory=list)  # [{index, png_url}]
    prompt:   str = ""
    error:    str = ""


# ── Style hints (extensible, admin-tunable in v2) ──────────────────────────
_STYLE_HINTS = {
    "natural": "3D-rendered natural landscape, soft daylight, realistic lighting, cinematic depth of field",
    "luxury":  "editorial magazine photography, marble surfaces, gold accents, dramatic studio lighting",
    "modern":  "minimalist design, clean composition, flat gradient background, Nordic aesthetic",
    "playful": "vibrant colors, illustrative style, cheerful mood, confetti and floral accents",
    "heritage":"ink painting influence, traditional Chinese aesthetics, Song dynasty landscape",
}

_EVENT_SCENE_HINTS = {
    # Seasonal terms (24 节气)
    "立春": "early spring scenery, budding willows, light green fields, pale sunrise",
    "春分": "cherry blossoms in soft breeze, warm afternoon light",
    "清明": "misty green mountains, light rain, fresh grass and willows",
    "谷雨": "gentle spring rain, lush green mountains, raindrops on petals, misty atmosphere",
    "立夏": "bamboo forest, warm morning sun, young leaves, blue sky",
    "夏至": "sunflowers and clear summer sky, golden light",
    "秋分": "harvest fields, golden rice, amber sunset",
    "霜降": "red maple leaves, frost on grass, cold morning mist",
    "立冬": "first snow on pine branches, tranquil winter landscape",
    "冬至": "snow-covered village, warm lantern glow, night sky",
    # Festivals
    "春节": "red lanterns, firework particles, auspicious clouds, jubilant atmosphere",
    "中秋": "full moon over mountains, osmanthus flowers, jade rabbit silhouette",
    "端午": "dragon boats, emerald green rivers, zongzi leaves",
    "元宵": "glowing lanterns, night sky, cheerful crowd silhouettes",
}


def build_poster_prompt(
    *,
    brand_name: str,
    event_keyword: str,
    style: str,
    industry: Optional[str] = None,
    primary_color: Optional[str] = None,
    product_description: Optional[str] = None,
) -> str:
    """Compose a single-image prompt suitable for DALL-E / FLUX / 即梦."""
    style_hint = _STYLE_HINTS.get(style, _STYLE_HINTS["natural"])
    scene_hint = _EVENT_SCENE_HINTS.get(event_keyword, "")
    color_hint = f"Primary color theme {primary_color}. " if primary_color else ""
    industry_hint = f"Industry: {industry}. " if industry else ""
    product_hint  = f"Feature a {product_description} as focal product. " if product_description else ""

    # Portrait composition explicit — text will be added in later layer (keep clean).
    return (
        f"Professional Chinese commercial poster for {brand_name}, themed on 『{event_keyword}』. "
        f"{industry_hint}{product_hint}"
        f"{scene_hint}. {style_hint}. {color_hint}"
        "Vertical 9:16 composition, elegant, magazine-cover quality, no text or watermark, "
        "leaves the upper third empty for headline typography. Ultra-detailed, 8K, sharp focus."
    )


# ── Base provider ──────────────────────────────────────────────────────────
class BasePosterProvider:
    name: str = "base"

    async def generate(self, *, prompt: str, size: tuple[int, int],
                       variant_count: int, api_key: str, cfg: Dict[str, Any]) -> PosterResult:
        raise NotImplementedError


def _get_proxy() -> Optional[str]:
    return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


# ── OpenAI-compatible (dall-e-3 / gpt-image-1 / 豆包 / 即梦 openai-compat) ──
class OpenAIPosterProvider(BasePosterProvider):
    name = "openai"

    async def generate(self, *, prompt, size, variant_count, api_key, cfg):
        if not api_key:
            return PosterResult(success=False, provider=self.name, error="OpenAI API key not configured")
        base_url = (cfg.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
        model    = cfg.get("openai_model") or "dall-e-3"

        # DALL-E 3 supports 1024x1792 (portrait), 1792x1024 (landscape), or 1024x1024.
        # For portrait 9:16, pick 1024x1792 and let the compositor upscale if needed.
        w, h = size
        if w < h:
            openai_size = "1024x1792"
        elif w > h:
            openai_size = "1792x1024"
        else:
            openai_size = "1024x1024"

        variants = []
        async with httpx.AsyncClient(timeout=120, proxy=_get_proxy()) as client:
            # DALL-E 3 only supports n=1 per call — loop
            for i in range(max(1, variant_count)):
                try:
                    r = await client.post(
                        f"{base_url}/images/generations",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model, "prompt": prompt, "size": openai_size,
                              "n": 1, "quality": "hd"},
                    )
                    if r.status_code >= 400:
                        return PosterResult(
                            success=False, provider=self.name,
                            error=f"[{r.status_code}] {r.text[:300]}",
                        )
                    data = r.json()
                    url = (data.get("data") or [{}])[0].get("url")
                    b64 = (data.get("data") or [{}])[0].get("b64_json")
                    if url:
                        variants.append({"index": i, "png_url": url})
                    elif b64:
                        variants.append({"index": i, "png_b64": b64})
                except Exception as e:                                # noqa: BLE001
                    return PosterResult(success=False, provider=self.name, error=str(e))
        if not variants:
            return PosterResult(success=False, provider=self.name, error="No image returned")
        return PosterResult(success=True, provider=self.name, variants=variants, prompt=prompt)


# ── FLUX via Replicate ─────────────────────────────────────────────────────
class FluxPosterProvider(BasePosterProvider):
    name = "flux"
    BASE = "https://api.replicate.com/v1"

    async def generate(self, *, prompt, size, variant_count, api_key, cfg):
        if not api_key:
            return PosterResult(success=False, provider=self.name, error="FLUX API key not configured")
        model = cfg.get("flux_model") or "black-forest-labs/flux-1.1-pro"
        w, h = size
        aspect_ratio = f"{w}:{h}"

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "input": {
                "prompt":       prompt,
                "aspect_ratio": aspect_ratio,
                "num_outputs":  max(1, min(4, variant_count)),
                "output_format":"png",
                "safety_tolerance": 2,
            }
        }

        async with httpx.AsyncClient(timeout=240, proxy=_get_proxy()) as client:
            try:
                r = await client.post(f"{self.BASE}/models/{model}/predictions",
                                      headers=headers, json=body)
                if r.status_code >= 400:
                    return PosterResult(success=False, provider=self.name,
                                         error=f"[{r.status_code}] {r.text[:300]}")
                pred = r.json()
                get_url = pred.get("urls", {}).get("get")
                if not get_url:
                    return PosterResult(success=False, provider=self.name,
                                         error="Replicate: no poll url returned")

                # Poll up to 5 minutes
                for _ in range(60):
                    await asyncio.sleep(5)
                    p = await client.get(get_url, headers=headers)
                    if p.status_code >= 400:
                        continue
                    data = p.json()
                    if data.get("status") == "succeeded":
                        out = data.get("output") or []
                        if isinstance(out, str):
                            out = [out]
                        variants = [{"index": i, "png_url": u} for i, u in enumerate(out)]
                        return PosterResult(success=True, provider=self.name,
                                             variants=variants, prompt=prompt)
                    if data.get("status") == "failed":
                        return PosterResult(success=False, provider=self.name,
                                             error=data.get("error", "FLUX generation failed"))
                return PosterResult(success=False, provider=self.name, error="FLUX generation timeout")
            except Exception as e:                                    # noqa: BLE001
                return PosterResult(success=False, provider=self.name, error=str(e))


# ── 即梦 (ByteDance Jimeng) — OpenAI-compat endpoint ──────────────────────
class JimengPosterProvider(BasePosterProvider):
    """Wraps 即梦's OpenAI-compat image endpoint. Same protocol as OpenAI but
    with a different base_url; ideal for Chinese scene understanding."""
    name = "jimeng"

    async def generate(self, *, prompt, size, variant_count, api_key, cfg):
        if not api_key:
            return PosterResult(success=False, provider=self.name, error="即梦 API key not configured")

        # Jimeng supports 9:16 directly
        w, h = size
        if w == h:
            js_size = "1024x1024"
        elif w > h:
            js_size = "1792x1024"
        else:
            js_size = "1024x1792"

        base_url = "https://ark.cn-beijing.volces.com/api/v3"
        model = cfg.get("jimeng_model") or "jimeng-3.0"

        variants = []
        async with httpx.AsyncClient(timeout=180, proxy=_get_proxy()) as client:
            for i in range(max(1, variant_count)):
                try:
                    r = await client.post(
                        f"{base_url}/images/generations",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model, "prompt": prompt, "size": js_size, "n": 1},
                    )
                    if r.status_code >= 400:
                        return PosterResult(success=False, provider=self.name,
                                             error=f"[{r.status_code}] {r.text[:300]}")
                    data = r.json()
                    items = data.get("data") or []
                    if items and items[0].get("url"):
                        variants.append({"index": i, "png_url": items[0]["url"]})
                except Exception as e:                                # noqa: BLE001
                    return PosterResult(success=False, provider=self.name, error=str(e))
        if not variants:
            return PosterResult(success=False, provider=self.name, error="No image returned")
        return PosterResult(success=True, provider=self.name, variants=variants, prompt=prompt)


# ── Factory + chain ────────────────────────────────────────────────────────
_PROVIDERS = {
    "openai": OpenAIPosterProvider,
    "flux":   FluxPosterProvider,
    "jimeng": JimengPosterProvider,
}


def _api_key_for(name: str, cfg: Dict[str, Any]) -> str:
    return {
        "openai": cfg.get("openai_api_key", ""),
        "flux":   cfg.get("flux_api_key", ""),
        "jimeng": cfg.get("jimeng_api_key", ""),
    }.get(name, "")


def _build(name: str, cfg: Dict[str, Any]) -> Optional[BasePosterProvider]:
    cls = _PROVIDERS.get(name)
    if not cls:
        return None
    if not _api_key_for(name, cfg):
        return None
    return cls()


async def generate_via_providers(
    *,
    brand_name: str,
    event_keyword: str,
    style: str,
    variant_count: int,
    size: tuple[int, int],
    industry: Optional[str] = None,
    primary_color: Optional[str] = None,
    product_description: Optional[str] = None,
    db=None,
) -> tuple[PosterResult, str]:
    """Try primary → fallback → openai. Returns first successful result."""
    from services.poster_settings import load_config
    cfg = load_config(db)

    prompt = build_poster_prompt(
        brand_name=brand_name, event_keyword=event_keyword,
        style=style, industry=industry, primary_color=primary_color,
        product_description=product_description,
    )

    primary  = cfg.get("provider") or "openai"
    fallback = cfg.get("fallback") or "openai"

    chain: List[BasePosterProvider] = []
    seen = set()
    for nm in (primary, fallback, "openai"):
        if nm in seen:
            continue
        p = _build(nm, cfg)
        if p:
            chain.append(p)
            seen.add(nm)

    last_err = ""
    for provider in chain:
        print(f"[PosterProvider] → trying {provider.name}")
        result = await provider.generate(
            prompt=prompt, size=size,
            variant_count=variant_count,
            api_key=_api_key_for(provider.name, cfg),
            cfg=cfg,
        )
        if result.success:
            print(f"[PosterProvider] ✓ {provider.name} succeeded ({len(result.variants)} variants)")
            return result, provider.name
        print(f"[PosterProvider] ✗ {provider.name} failed: {result.error}")
        last_err = result.error

    return PosterResult(success=False, provider="none",
                         error=f"All providers failed. Last: {last_err}"), "none"


def list_providers(db=None) -> List[Dict[str, Any]]:
    from services.poster_settings import load_config
    cfg = load_config(db)
    primary = cfg.get("provider") or "openai"
    fallback = cfg.get("fallback") or "openai"
    labels = {
        "openai": "OpenAI / 豆包 (图像)",
        "flux":   "FLUX (Replicate)",
        "jimeng": "即梦 (ByteDance)",
    }
    rows = []
    for name in _PROVIDERS.keys():
        rows.append({
            "name":       name,
            "label":      labels.get(name, name),
            "configured": bool(_api_key_for(name, cfg)),
            "role":       "primary" if primary == name else ("fallback" if fallback == name else None),
        })
    return rows


async def test_provider(name: str, db=None) -> Dict[str, Any]:
    from services.poster_settings import load_config, get_size
    cfg = load_config(db)
    p = _build(name, cfg)
    if not p:
        return {"success": False, "error": f"Provider {name} not configured"}
    result = await p.generate(
        prompt="Test poster: minimal soft-lit Chinese traditional landscape, 9:16 portrait, no text",
        size=get_size(cfg, "story"),
        variant_count=1,
        api_key=_api_key_for(name, cfg),
        cfg=cfg,
    )
    return {
        "success":  result.success,
        "provider": result.provider,
        "variants": result.variants,
        "error":    result.error,
    }
