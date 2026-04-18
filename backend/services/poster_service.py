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


# ── Soft gradient for legibility (no hard rectangles) ────────────────────
def _apply_gradient_strip(canvas: Image.Image, rect: Tuple[int, int, int, int],
                          max_alpha: int = 140, direction: str = "bottom") -> None:
    """Paint a transparent→dark gradient strip for text legibility.

    `direction="bottom"` = opaque at the outer edge fading inward. Much softer
    than a hard semi-transparent rectangle.
    """
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    if direction in ("top", "bottom"):
        for i in range(h):
            t = i / max(1, h - 1)
            # Ease-in curve so the fade is smooth, not linear
            alpha = int(max_alpha * (t if direction == "bottom" else (1 - t)) ** 1.8)
            sd.line([(0, i), (w, i)], fill=(0, 0, 0, alpha))
    canvas.alpha_composite(strip, (x0, y0))


# ── Compositor (soft / editorial style) ─────────────────────────────────
def compose_poster(
    *,
    background: Image.Image,
    target_size: Tuple[int, int],
    brand_name: str,
    headline: str = "",
    subline: str = "",
    event_date: str = "",
    logo: Optional[Image.Image] = None,
    product: Optional[Image.Image] = None,
    primary_color: Optional[str] = None,
    add_footer: bool = True,
) -> Image.Image:
    """Build the final poster from the AI-rendered background.

    Philosophy: trust the AI for typography + atmosphere. Our job here is
    only: (a) cover-fit, (b) optional product composite, (c) tiny brand tag
    in the corner, (d) subtle bottom gradient for legibility if needed.
    NO heavy black strips, NO stroked headline text stamping.
    """
    W, H = target_size

    # ── 1. Cover-fit the background ───────────────────────────────────
    bg = background.copy().convert("RGBA")
    bw, bh = bg.size
    scale = max(W / bw, H / bh)
    new_w, new_h = int(bw * scale), int(bh * scale)
    bg = bg.resize((new_w, new_h), Image.LANCZOS)
    off_x = (new_w - W) // 2
    off_y = (new_h - H) // 2
    canvas = bg.crop((off_x, off_y, off_x + W, off_y + H)).convert("RGBA")

    # ── 2. Optional product image composite (center-lower) ────────────
    if product is not None:
        try:
            pw, ph = product.size
            # Target: up to 52% of canvas width, keep aspect, leave room at bottom
            max_w = int(W * 0.52)
            max_h = int(H * 0.42)
            pscale = min(max_w / pw, max_h / ph)
            tw, th = int(pw * pscale), int(ph * pscale)
            product_resized = product.resize((tw, th), Image.LANCZOS)

            # Soft drop shadow for natural "sitting on surface" feel
            shadow = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.ellipse((0, int(th * 0.88), tw, int(th * 1.05)),
                       fill=(0, 0, 0, 90))
            try:
                from PIL import ImageFilter
                shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(tw * 0.04)))
            except Exception:
                pass

            px = (W - tw) // 2
            py = int(H * 0.50)   # center-lower
            canvas.alpha_composite(shadow, (px, py + int(th * 0.05)))
            canvas.alpha_composite(product_resized, (px, py))
        except Exception as e:                                        # noqa: BLE001
            print(f"[poster_service] product paste failed: {e}")

    # ── 3. Minimal brand mark (bottom-right, small) + optional date ──
    if add_footer:
        # Subtle bottom gradient for legibility (not a hard black strip)
        _apply_gradient_strip(canvas, (0, int(H * 0.88), W, H),
                               max_alpha=120, direction="bottom")

        # Accent tick + brand text, small, bottom-right
        accent_hex = primary_color or "#ffffff"
        try:
            r = int(accent_hex[1:3], 16); g = int(accent_hex[3:5], 16); b = int(accent_hex[5:7], 16)
        except Exception:                                             # noqa: BLE001
            r, g, b = 255, 255, 255

        draw = ImageDraw.Draw(canvas, "RGBA")
        brand_tag_size = max(18, int(W * 0.013))
        font_brand = _load_font(int(brand_tag_size * 1.3), bold=True)
        font_date  = _load_font(brand_tag_size)

        # Small accent bar (4px × 32px) before brand name
        bar_x = int(W * 0.06)
        bar_y = int(H * 0.95)
        draw.rectangle((bar_x, bar_y, bar_x + int(W * 0.02), bar_y + 3),
                       fill=(r, g, b, 220))

        if event_date:
            draw.text((bar_x, bar_y + 8),
                      event_date, font=font_date, fill=(255, 255, 255, 210))

        if brand_name:
            try:
                bbox = draw.textbbox((0, 0), brand_name, font=font_brand)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(brand_name) * brand_tag_size
            # Right-aligned, soft white with slight shadow for legibility
            tx = W - tw - int(W * 0.06)
            ty = int(H * 0.94)
            # Shadow
            draw.text((tx + 1, ty + 1), brand_name, font=font_brand,
                      fill=(0, 0, 0, 150))
            draw.text((tx, ty), brand_name, font=font_brand,
                      fill=(255, 255, 255, 240))

        # Optional small logo bottom-left (if provided and no date)
        if logo is not None and not event_date:
            try:
                logo_target_h = int(W * 0.035)
                lw, lh = logo.size
                logo_target_w = int(lw * logo_target_h / lh)
                logo_resized = logo.resize((logo_target_w, logo_target_h), Image.LANCZOS)
                canvas.alpha_composite(
                    logo_resized,
                    (bar_x + int(W * 0.025), int(H * 0.94))
                )
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
    product_image_url: Optional[str] = None,
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

    # ── Load user product image if provided ────────────────────────────
    product_img: Optional[Image.Image] = None
    if product_image_url:
        # If it's a local /api/poster/product/... URL, resolve to file path
        if product_image_url.startswith("/api/poster/product/"):
            fname = product_image_url.split("/")[-1].split("?")[0]
            local_path = os.path.join(UPLOAD_DIR, "poster_products", fname)
            if os.path.exists(local_path):
                try:
                    product_img = Image.open(local_path).convert("RGBA")
                except Exception as e:
                    print(f"[poster_service] local product load failed: {e}")
        else:
            # External URL — download it
            product_img = await _download_image(product_image_url)

    try:
        # 1. Generate background (pass slogan + product hint into AI prompt)
        result, provider_name = await generate_via_providers(
            brand_name=brand_name,
            event_keyword=event_keyword or "",
            style=style,
            variant_count=variant_count,
            size=target_size,
            industry=industry,
            primary_color=primary_color,
            product_description=product_description,
            headline=headline or None,
            subline=subline or None,
            has_product_image=product_img is not None,
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

        # Headline/subline are now baked into AI prompt — compositor only adds
        # tiny brand tag + optional product. Clean and editorial.
        final_date = (event_date or datetime.now().strftime("%Y.%m.%d")).strip()

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
                headline="",          # AI renders headline inside the image
                subline="",           # same
                event_date=final_date,
                logo=None,
                product=product_img,  # user-uploaded product (optional)
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
