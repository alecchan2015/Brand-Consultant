"""
End-to-end poster generation pipeline.

Stages:
    1. Resolve brand context (color, logo) — from user profile / passed overrides
    2. Call poster_providers.generate_via_providers() → background image URL
    3. Download, optional product-cutout overlay (future: Remove.bg layer)
    4. Pillow compositor adds:
         - Headline text at top (Chinese-aware)
         - Subline / event date
         - Brand logo at bottom-left
         - Footer strip with brand info (optional)
    5. Save PNG to uploads, update PosterGeneration row
"""
from __future__ import annotations

import asyncio
import base64
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageDraw, ImageFont

from sqlalchemy.orm import Session


UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


# ── Font resolution ────────────────────────────────────────────────────────
def _find_chinese_font() -> Optional[str]:
    """Locate a font that supports Chinese. Docker image ships fonts-wqy-microhei."""
    candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",                        # macOS
        "/System/Library/Fonts/STHeiti Medium.ttc",                  # macOS fallback
        "C:\\Windows\\Fonts\\msyh.ttc",                              # Windows
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = _find_chinese_font()
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:                                             # noqa: BLE001
            pass
    return ImageFont.load_default()


# ── Image fetch utilities ──────────────────────────────────────────────────
async def _download_image(url: str) -> Optional[Image.Image]:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    try:
        async with httpx.AsyncClient(timeout=120, proxy=proxy, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:                                            # noqa: BLE001
        print(f"[poster_service] download failed {url}: {e}")
        return None


def _image_from_b64(b64: str) -> Optional[Image.Image]:
    try:
        raw = base64.b64decode(b64)
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as e:                                            # noqa: BLE001
        print(f"[poster_service] b64 decode failed: {e}")
        return None


# ── Text layout helpers ────────────────────────────────────────────────────
def _draw_text_centered(
    draw: ImageDraw.ImageDraw, text: str,
    box: Tuple[int, int, int, int], font, fill=(255, 255, 255, 255),
    stroke_width: int = 0, stroke_fill=(0, 0, 0, 180),
) -> None:
    """Draw text centered inside `box = (x0, y0, x1, y1)`."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
    except Exception:
        # Fallback for older Pillow
        tw, th = font.getsize(text) if hasattr(font, "getsize") else (0, 0)
        bbox = (0, 0, tw, th)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx = box[0] + (box[2] - box[0] - tw) // 2 - bbox[0]
    cy = box[1] + (box[3] - box[1] - th) // 2 - bbox[1]
    draw.text((cx, cy), text, font=font, fill=fill,
              stroke_width=stroke_width, stroke_fill=stroke_fill)


def _rounded_rectangle(draw: ImageDraw.ImageDraw, xy, radius: int, fill):
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
    except Exception:
        draw.rectangle(xy, fill=fill)


# ── Compositor ─────────────────────────────────────────────────────────────
def compose_poster(
    *,
    background: Image.Image,
    target_size: Tuple[int, int],
    brand_name: str,
    headline: str,
    subline: str,
    event_date: str,
    logo: Optional[Image.Image] = None,
    primary_color: Optional[str] = None,
    add_footer: bool = True,
) -> Image.Image:
    """Build the final poster from a background image + overlays."""
    W, H = target_size
    # Cover-fit the background
    bg = background.copy().convert("RGBA")
    bw, bh = bg.size
    scale = max(W / bw, H / bh)
    new_w, new_h = int(bw * scale), int(bh * scale)
    bg = bg.resize((new_w, new_h), Image.LANCZOS)
    off_x = (new_w - W) // 2
    off_y = (new_h - H) // 2
    bg = bg.crop((off_x, off_y, off_x + W, off_y + H))

    canvas = bg.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")

    # ── Headline strip (top 28% with soft gradient for legibility) ────────
    # Scale font size proportionally to canvas width
    headline_size   = max(72, int(W * 0.095))
    subline_size    = max(28, int(W * 0.028))
    footer_size     = max(22, int(W * 0.016))
    brand_tag_size  = max(20, int(W * 0.014))

    if headline:
        _rounded_rectangle(draw, (0, 0, W, int(H * 0.22)), radius=0,
                            fill=(0, 0, 0, 70))  # subtle top darken
        font_head = _load_font(headline_size, bold=True)
        _draw_text_centered(
            draw, headline,
            (int(W * 0.08), int(H * 0.05), int(W * 0.92), int(H * 0.16)),
            font_head, fill=(255, 255, 255, 255),
            stroke_width=2, stroke_fill=(0, 0, 0, 140),
        )

    if subline:
        font_sub = _load_font(subline_size)
        _draw_text_centered(
            draw, subline,
            (int(W * 0.1), int(H * 0.165), int(W * 0.9), int(H * 0.205)),
            font_sub, fill=(255, 255, 255, 230),
        )

    # ── Footer strip (bottom ~12%) with brand bar ────────────────────────
    if add_footer:
        footer_h = int(H * 0.12)
        # semi-transparent dark strip with optional primary-color accent
        strip_color = (0, 0, 0, 180)
        _rounded_rectangle(draw, (0, H - footer_h, W, H), radius=0,
                            fill=strip_color)

        # Accent line at top of footer
        accent_hex = primary_color or "#6366f1"
        try:
            r = int(accent_hex[1:3], 16); g = int(accent_hex[3:5], 16); b = int(accent_hex[5:7], 16)
        except Exception:                                             # noqa: BLE001
            r, g, b = 99, 102, 241
        draw.rectangle((0, H - footer_h, W, H - footer_h + 3), fill=(r, g, b, 255))

        # Brand name in footer (right side)
        font_brand = _load_font(footer_size, bold=True)
        font_date  = _load_font(brand_tag_size)
        brand_text = brand_name
        # Right-aligned
        try:
            bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(brand_text) * footer_size
        draw.text((W - tw - int(W * 0.04), H - footer_h + int(footer_h * 0.3)),
                  brand_text, font=font_brand, fill=(255, 255, 255, 255))
        if event_date:
            draw.text((int(W * 0.04), H - footer_h + int(footer_h * 0.35)),
                      event_date, font=font_date, fill=(255, 255, 255, 200))

        # Logo in footer left-center (if provided)
        if logo is not None:
            try:
                logo_target_h = int(footer_h * 0.55)
                lw, lh = logo.size
                logo_target_w = int(lw * logo_target_h / lh)
                logo_resized = logo.resize((logo_target_w, logo_target_h), Image.LANCZOS)
                canvas.paste(logo_resized,
                             (int(W * 0.04) + 0, H - footer_h + (footer_h - logo_target_h) // 2 - int(brand_tag_size * 1.4)),
                             logo_resized)
            except Exception as e:                                    # noqa: BLE001
                print(f"[poster_service] logo paste failed: {e}")

    return canvas.convert("RGB")


# ── Public entry point (called from background thread) ────────────────────
async def generate_poster_full(
    *,
    db: Session,
    gen_id: int,
    brand_name: str,
    event_keyword: str,
    headline: Optional[str] = None,
    subline: Optional[str] = None,
    event_date: Optional[str] = None,
    industry: Optional[str] = None,
    style: str = "natural",
    size_key: str = "portrait",
    primary_color: Optional[str] = None,
    product_description: Optional[str] = None,
    variant_count: int = 1,
    user_id: Optional[int] = None,
) -> None:
    """Run the full pipeline. Updates the PosterGeneration row as it goes."""
    from models import PosterGeneration
    from services.poster_providers import generate_via_providers
    from services.poster_settings import load_config, get_size
    from services.file_service import sanitize_filename, ensure_upload_dir

    ensure_upload_dir()
    cfg = load_config(db)
    target_size = get_size(cfg, size_key)

    gen = db.query(PosterGeneration).filter(PosterGeneration.id == gen_id).first()
    if not gen:
        return

    try:
        # 1. Generate background
        result, provider_name = await generate_via_providers(
            brand_name=brand_name,
            event_keyword=event_keyword or "",
            style=style,
            variant_count=variant_count,
            size=target_size,
            industry=industry,
            primary_color=primary_color,
            product_description=product_description,
            db=db,
        )
        if not result.success or not result.variants:
            gen.status = "failed"
            gen.error_msg = result.error or "No variants returned"
            gen.provider = provider_name
            db.commit()
            return

        gen.provider = provider_name
        gen.prompt_optimized = result.prompt
        db.commit()

        # 2. Compose each variant
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_brand = sanitize_filename(brand_name)
        saved_variants = []

        # Headline defaults: use event_keyword if user didn't provide one
        final_headline = (headline or event_keyword or brand_name).strip()
        final_subline  = (subline or "").strip()
        final_date     = (event_date or datetime.now().strftime("%Y.%m.%d")).strip()

        # Load brand logo if we have one cached (future: pull from brand assets)
        # For now, skip — logo overlay optional.

        for variant in result.variants:
            bg_img = None
            if variant.get("png_url"):
                bg_img = await _download_image(variant["png_url"])
            elif variant.get("png_b64"):
                bg_img = _image_from_b64(variant["png_b64"])
            if bg_img is None:
                continue

            poster = compose_poster(
                background=bg_img,
                target_size=target_size,
                brand_name=brand_name,
                headline=final_headline,
                subline=final_subline,
                event_date=final_date,
                logo=None,
                primary_color=primary_color,
                add_footer=cfg.get("add_footer", True),
            )

            # Save
            idx = variant.get("index", 0)
            suffix = f"_v{idx+1}" if len(result.variants) > 1 else ""
            fname = f"{safe_brand}_poster_{event_keyword or 'event'}{suffix}_{timestamp}.png"
            fpath = os.path.join(UPLOAD_DIR, fname)
            poster.save(fpath, format="PNG", optimize=True)
            saved_variants.append({
                "index": idx,
                "png_url": f"/api/poster/file/{fname}",   # served via FileResponse; simple
                "png_path": fpath,
            })

        if not saved_variants:
            gen.status = "failed"
            gen.error_msg = "No variants produced after composition"
            db.commit()
            return

        # Primary path = first variant
        gen.png_path = saved_variants[0]["png_path"]
        gen.variants = [{"index": v["index"], "png_url": v["png_url"]}
                        for v in saved_variants]
        gen.status = "done"
        gen.completed_at = datetime.utcnow()
        db.commit()
    except Exception as e:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        gen.status = "failed"
        gen.error_msg = str(e)[:500]
        db.commit()
