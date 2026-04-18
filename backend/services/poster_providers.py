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
    headline: Optional[str] = None,
    subline: Optional[str] = None,
    has_product_image: bool = False,
) -> str:
    """Compose a single-image prompt — bakes slogan and atmosphere directly into
    the AI render so the output is editorial, not template-stamped."""
    style_hint = _STYLE_HINTS.get(style, _STYLE_HINTS["natural"])
    scene_hint = _EVENT_SCENE_HINTS.get(event_keyword, "")
    color_hint = f"Primary color accent {primary_color}. " if primary_color else ""
    industry_hint = f"Industry context: {industry}. " if industry else ""
    product_hint = (
        f"Feature a {product_description} as focal product. "
        if product_description else ""
    )

    # If user uploaded a product image we'll composite it ourselves; ask AI to
    # leave the center-lower area clean for the product placement.
    product_area_hint = (
        "Keep the lower-middle third of the composition uncluttered — "
        "reserve a clean, softly lit area for a product placement that will be "
        "composited in post. "
        if has_product_image else ""
    )

    # If headline/slogan provided, allow the AI to render it elegantly as part
    # of the photograph (editorial magazine style) rather than us stamping it.
    text_hint = ""
    if headline:
        if subline:
            text_hint = (
                f"Include elegant Chinese editorial typography that reads "
                f"『{headline}』 as the hero line and 『{subline}』 as a smaller "
                f"supporting line, positioned in the upper third, "
                f"lightly integrated into the scene — soft serif / brush feel, "
                f"NOT a watermark, NOT a sticker, look like high-end magazine cover. "
            )
        else:
            text_hint = (
                f"Include elegant Chinese editorial typography that reads "
                f"『{headline}』, positioned in the upper third, feeling like a "
                f"magazine cover headline — soft, refined, part of the composition. "
            )

    return (
        f"Ultra-premium commercial magazine poster for the brand {brand_name}, "
        f"themed around 『{event_keyword}』. "
        f"{industry_hint}{product_hint}"
        f"{scene_hint}. {style_hint}. {color_hint}"
        f"{text_hint}{product_area_hint}"
        "Vertical 9:16 editorial composition, natural lighting, film photography "
        "aesthetic, soft depth of field, cinematic atmosphere. "
        "Avoid: harsh overlays, sticker-like text, watermarks, flat template look. "
        "Feel like a real Vogue-quality magazine cover with integrated typography. "
        "Ultra-detailed, 8K, editorial grade."
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


# ── 即梦 (ByteDance Jimeng) ────────────────────────────────────────────────
class JimengPosterProvider(BasePosterProvider):
    """Dual-mode adapter for 即梦 (Volcengine 火山引擎):

    - If model starts with `doubao-seedream-*` or `jimeng-*` → OpenAI-compat
      ARK endpoint at `ark.cn-beijing.volces.com/api/v3` with Bearer token.
      This is the preferred path and supports 即梦 3.0 & 4.0.

    - If model starts with `high_aes_general_v*` → Volcengine CV API at
      `visual.volcengineapi.com` with SigV4-style HMAC-SHA256 signing
      (Action=CVProcess, Version=2022-08-31). Needs access_key + secret_key.
    """
    name = "jimeng"

    async def generate(self, *, prompt, size, variant_count, api_key, cfg):
        model = cfg.get("jimeng_model") or "doubao-seedream-4-0-250828"

        # Route: CV API vs ARK OpenAI-compat
        if model.startswith("high_aes_general_") or model.startswith("jimeng_high_aes_"):
            return await self._generate_cv_api(prompt, size, variant_count, model, cfg)
        return await self._generate_ark(prompt, size, variant_count, model, api_key)

    async def _generate_ark(self, prompt, size, variant_count, model, api_key):
        # Aggressive sanitization — users often paste keys with surrounding
        # whitespace, quotes, or mask artifacts.
        api_key = (api_key or "").strip().strip('"').strip("'")
        if not api_key:
            return PosterResult(success=False, provider=self.name,
                                 error="即梦 API key 未配置")
        if "..." in api_key:
            return PosterResult(success=False, provider=self.name,
                                 error="API key 似乎是脱敏占位符（含 ...），请重新粘贴原始密钥后再保存")

        # ARK API key format check — should look like an ASCII token;
        # warn early if user entered something that looks wrong.
        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."
               for c in api_key):
            return PosterResult(success=False, provider=self.name,
                                 error=(
                                     "API key 含非法字符（空格/中文等）。"
                                     "请到 https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey "
                                     "复制正确的 ARK API Key（不是 AK/SK，也不是账户密码）"
                                 ))

        w, h = size
        # Seedream 4.0 supports native portrait 9:16 (1152x2048, 1536x2560, 2304x4096)
        # We request the closest preset, then upscale in compositor.
        if w == h:
            ark_size = "2048x2048"
        elif w > h:
            ark_size = "2048x1152"  # 16:9 approx
        else:
            ark_size = "1536x2560"  # 9:16 high-quality

        base_url = "https://ark.cn-beijing.volces.com/api/v3"

        variants = []
        async with httpx.AsyncClient(timeout=240, proxy=_get_proxy()) as client:
            for i in range(max(1, variant_count)):
                try:
                    r = await client.post(
                        f"{base_url}/images/generations",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model, "prompt": prompt, "size": ark_size, "n": 1},
                    )
                    if r.status_code == 401:
                        # Authoritative message for the user
                        return PosterResult(success=False, provider=self.name, error=(
                            f"[401] ARK 鉴权失败。"
                            f"请确认使用的是 ARK API Key（格式通常为 UUID 或以 `sk-` 开头），"
                            f"而不是火山引擎账户的 Access Key / Secret Key。"
                            f"获取地址: https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey  "
                            f"[原始响应] {r.text[:200]}"
                        ))
                    if r.status_code >= 400:
                        return PosterResult(success=False, provider=self.name,
                                             error=f"[{r.status_code}] {r.text[:300]}")
                    data = r.json()
                    items = data.get("data") or []
                    if items and items[0].get("url"):
                        variants.append({"index": i, "png_url": items[0]["url"]})
                    elif items and items[0].get("b64_json"):
                        variants.append({"index": i, "png_b64": items[0]["b64_json"]})
                except Exception as e:                                # noqa: BLE001
                    return PosterResult(success=False, provider=self.name, error=str(e))
        if not variants:
            return PosterResult(success=False, provider=self.name, error="No image returned")
        return PosterResult(success=True, provider=self.name, variants=variants, prompt=prompt)

    async def _generate_cv_api(self, prompt, size, variant_count, req_key, cfg):
        """Official Volcengine CV API path (visual.volcengineapi.com).

        Uses Volc SigV4 HMAC-SHA256. Requires access_key + secret_key in cfg
        (not the ARK api_key / Bearer token).
        """
        ak = cfg.get("jimeng_access_key", "") or cfg.get("jimeng_api_key", "")
        sk = cfg.get("jimeng_secret_key", "")
        if not ak or not sk:
            return PosterResult(success=False, provider=self.name,
                                 error=f"CV API {req_key} 需要配置 jimeng_access_key + jimeng_secret_key")

        import hashlib, hmac, json as _json
        from datetime import datetime as _dt

        w, h = size
        # Clamp to CV API supported range (max 2048 per side)
        tw = min(w, 2048)
        th = min(h, 2048)
        payload = {
            "req_key":  req_key,
            "prompt":   prompt,
            "width":    tw,
            "height":   th,
            "seed":     -1,
            "scale":    3.5,
            "use_sr":   True,
            "return_url": True,
            "logo_info": {"add_logo": False},
        }
        body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")

        host = "visual.volcengineapi.com"
        service = "cv"
        region = "cn-north-1"
        algorithm = "HMAC-SHA256"
        now = _dt.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        canonical_uri = "/"
        canonical_querystring = f"Action=CVProcess&Version=2022-08-31"
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_headers = (
            f"content-type:application/json\n"
            f"host:{host}\n"
            f"x-content-sha256:{payload_hash}\n"
            f"x-date:{amz_date}\n"
        )
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = (
            f"POST\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )
        credential_scope = f"{date_stamp}/{region}/{service}/request"
        string_to_sign = (
            f"{algorithm}\n{amz_date}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        def _sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
        k_date = _sign(sk.encode("utf-8"), date_stamp)
        k_region = _sign(k_date, region)
        k_service = _sign(k_region, service)
        k_signing = _sign(k_service, "request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization = (
            f"{algorithm} Credential={ak}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        headers = {
            "Content-Type":      "application/json",
            "Host":               host,
            "X-Date":             amz_date,
            "X-Content-Sha256":   payload_hash,
            "Authorization":      authorization,
        }

        url = f"https://{host}/?{canonical_querystring}"
        try:
            async with httpx.AsyncClient(timeout=180, proxy=_get_proxy()) as client:
                r = await client.post(url, headers=headers, content=body)
                if r.status_code >= 400:
                    return PosterResult(success=False, provider=self.name,
                                         error=f"CV API [{r.status_code}] {r.text[:400]}")
                data = r.json()
                # Response: {"code":10000, "data":{"image_urls":["https://..."]}}
                code = data.get("code") or (data.get("ResponseMetadata") or {}).get("Error")
                if code and code != 10000:
                    return PosterResult(success=False, provider=self.name,
                                         error=f"CV API code={code}: {data.get('message', '')[:300]}")
                d = data.get("data") or {}
                urls = d.get("image_urls") or d.get("binary_data_base64") or []
                variants = []
                for i, item in enumerate(urls[:variant_count]):
                    if isinstance(item, str) and item.startswith("http"):
                        variants.append({"index": i, "png_url": item})
                    elif isinstance(item, str):
                        variants.append({"index": i, "png_b64": item})
                if not variants:
                    return PosterResult(success=False, provider=self.name,
                                         error=f"CV API no image returned: {str(data)[:200]}")
                return PosterResult(success=True, provider=self.name,
                                     variants=variants, prompt=prompt)
        except Exception as e:                                        # noqa: BLE001
            return PosterResult(success=False, provider=self.name, error=str(e))


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
    headline: Optional[str] = None,
    subline: Optional[str] = None,
    has_product_image: bool = False,
    db=None,
) -> tuple[PosterResult, str]:
    """Try primary → fallback → openai. Returns first successful result."""
    from services.poster_settings import load_config
    cfg = load_config(db)

    prompt = build_poster_prompt(
        brand_name=brand_name, event_keyword=event_keyword,
        style=style, industry=industry, primary_color=primary_color,
        product_description=product_description,
        headline=headline, subline=subline, has_product_image=has_product_image,
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
