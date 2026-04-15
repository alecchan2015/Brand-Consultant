import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")

# Ordered list of Chinese font paths (macOS, Linux, Windows)
CHINESE_FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",       # macOS Heiti (verified)
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def ensure_upload_dir():
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[^\w\u4e00-\u9fff\-_.]', '_', name)
    return name[:80]


def _find_chinese_font() -> Optional[str]:
    for fp in CHINESE_FONT_PATHS:
        if os.path.exists(fp):
            return fp
    return None


def _strip_markdown(text: str) -> str:
    """Remove markdown syntax from text for plain rendering."""
    # Bold/italic
    text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text.strip()


# ─────────────────────────────────────────────
# Markdown file
# ─────────────────────────────────────────────

def generate_markdown_file(
    task_id: int,
    agent_type: str,
    brand_name: str,
    content: str,
) -> tuple[str, str]:
    """Generate .md file and return (file_path, file_name)"""
    ensure_upload_dir()
    agent_names = {"strategy": "战略规划", "brand": "品牌设计", "operations": "运营实施"}
    agent_name = agent_names.get(agent_type, agent_type)
    safe_brand = sanitize_filename(brand_name or "品牌")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{safe_brand}_{agent_name}_{timestamp}.md"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    header = f"# {brand_name or '品牌'} - {agent_name}方案\n\n"
    header += f"> 生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n"
    header += f"> 本方案由AI专家生成，仅供参考\n\n---\n\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(header + content)

    return file_path, file_name


# ─────────────────────────────────────────────
# PDF file
# ─────────────────────────────────────────────

def generate_pdf_file(
    task_id: int,
    agent_type: str,
    brand_name: str,
    content: str,
) -> tuple[str, str]:
    """Generate PDF using ReportLab with Chinese font support."""
    ensure_upload_dir()
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    agent_names = {"strategy": "战略规划", "brand": "品牌设计", "operations": "运营实施"}
    agent_name = agent_names.get(agent_type, agent_type)
    safe_brand = sanitize_filename(brand_name or "品牌")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{safe_brand}_{agent_name}_{timestamp}.pdf"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    # Register Chinese font
    font_name = "Helvetica"
    font_path = _find_chinese_font()
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont("ChineseFont", font_path))
            font_name = "ChineseFont"
        except Exception as e:
            print(f"Font registration failed ({font_path}): {e}")

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    title_style = ParagraphStyle(
        "CustomTitle",
        fontName=font_name,
        fontSize=20,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=12,
        leading=30,
    )
    h1_style = ParagraphStyle(
        "H1",
        fontName=font_name,
        fontSize=16,
        textColor=colors.HexColor("#16213e"),
        spaceBefore=16,
        spaceAfter=8,
        leading=24,
    )
    h2_style = ParagraphStyle(
        "H2",
        fontName=font_name,
        fontSize=13,
        textColor=colors.HexColor("#0f3460"),
        spaceBefore=12,
        spaceAfter=6,
        leading=20,
    )
    h3_style = ParagraphStyle(
        "H3",
        fontName=font_name,
        fontSize=11,
        textColor=colors.HexColor("#0f3460"),
        spaceBefore=8,
        spaceAfter=4,
        leading=17,
    )
    body_style = ParagraphStyle(
        "Body",
        fontName=font_name,
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceAfter=6,
        leading=17,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        fontName=font_name,
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceAfter=4,
        leading=17,
        leftIndent=12,
        firstLineIndent=0,
    )
    meta_style = ParagraphStyle(
        "Meta",
        fontName=font_name,
        fontSize=9,
        textColor=colors.HexColor("#888888"),
        spaceAfter=4,
        leading=14,
    )
    quote_style = ParagraphStyle(
        "Quote",
        fontName=font_name,
        fontSize=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=4,
        leading=16,
        leftIndent=16,
    )

    story = []
    story.append(Paragraph(f"{brand_name or '品牌'} - {agent_name}方案", title_style))
    story.append(Paragraph(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}", meta_style))
    story.append(Paragraph("本方案由AI专家生成，仅供参考", meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e0e0e0"), spaceAfter=12))

    for line in content.split("\n"):
        line = line.rstrip()
        if not line:
            story.append(Spacer(1, 6))
            continue

        # Escape XML special chars for ReportLab BEFORE stripping markdown
        def xml_escape(s):
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if line.startswith("#### "):
            text = _strip_markdown(line[5:])
            story.append(Paragraph(xml_escape(text), h3_style))
        elif line.startswith("### "):
            text = _strip_markdown(line[4:])
            story.append(Paragraph(xml_escape(text), h2_style))
        elif line.startswith("## "):
            text = _strip_markdown(line[3:])
            story.append(Paragraph(xml_escape(text), h1_style))
        elif line.startswith("# "):
            text = _strip_markdown(line[2:])
            story.append(Paragraph(xml_escape(text), title_style))
        elif line.startswith("- ") or line.startswith("* "):
            text = _strip_markdown(line[2:])
            story.append(Paragraph(f"• {xml_escape(text)}", bullet_style))
        elif re.match(r'^\d+\.', line):
            text = _strip_markdown(line)
            story.append(Paragraph(xml_escape(text), bullet_style))
        elif line.startswith("---"):
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=6))
        elif line.startswith(">"):
            text = _strip_markdown(line[1:].strip())
            story.append(Paragraph(xml_escape(text), quote_style))
        else:
            text = _strip_markdown(line)
            story.append(Paragraph(xml_escape(text), body_style))

    doc.build(story)
    return file_path, file_name


# ─────────────────────────────────────────────
# PPTX file (strategy / operations / brand)
# ─────────────────────────────────────────────

async def generate_pptx_file(
    task_id: int,
    agent_type: str,
    brand_name: str,
    content: str,
    db=None,
) -> tuple[str, str]:
    """Generate professional PowerPoint using the multi-provider factory.

    Primary/fallback providers are selected by env (PPT_PROVIDER / PPT_FALLBACK);
    the chain always ends in the local python-pptx renderer so generation never
    hard-fails. See services/ppt_providers.py.
    """
    ensure_upload_dir()
    from services.ppt_providers import generate_via_providers

    agent_names = {"strategy": "战略规划", "brand": "品牌设计", "operations": "运营实施"}
    agent_name = agent_names.get(agent_type, agent_type)
    safe_brand = sanitize_filename(brand_name or "品牌")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{safe_brand}_{agent_name}_{timestamp}.pptx"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    await generate_via_providers(
        task_id=task_id,
        agent_type=agent_type,
        brand_name=brand_name or "品牌",
        content=content,
        file_path=file_path,
        db=db,
    )
    return file_path, file_name


# ─────────────────────────────────────────────
# Brand PNG
# ─────────────────────────────────────────────

def generate_brand_png(
    task_id: int,
    brand_name: str,
    content: str,
    logo_image=None,
) -> tuple[str, str]:
    """Generate brand style guide PNG using Pillow."""
    ensure_upload_dir()
    from PIL import Image, ImageDraw, ImageFont

    safe_brand = sanitize_filename(brand_name or "品牌")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{safe_brand}_品牌视觉_{timestamp}.png"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    img, draw = _render_brand_visual(brand_name, content, logo_image=logo_image)
    img.save(file_path, "PNG", quality=95)
    return file_path, file_name


# ─────────────────────────────────────────────
# Brand PSD (multi-layer for Photoshop)
# ─────────────────────────────────────────────

def generate_brand_psd(
    task_id: int,
    brand_name: str,
    content: str,
    logo_image=None,
) -> tuple[str, str]:
    """Generate a layered PSD file for Photoshop editing."""
    ensure_upload_dir()
    from PIL import Image, ImageDraw, ImageFont
    from psd_tools import PSDImage

    safe_brand = sanitize_filename(brand_name or "品牌")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{safe_brand}_品牌视觉_{timestamp}.psd"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    W, H = 1920, 1080

    # Extract brand colors from content
    hex_colors = re.findall(r'#([A-Fa-f0-9]{6})', content)
    brand_colors = ["#" + c for c in hex_colors[:5]] if hex_colors else [
        "#1a1a2e", "#16213e", "#0f3460", "#e94560", "#f5f5f5"
    ]
    while len(brand_colors) < 5:
        brand_colors.append("#cccccc")

    font_path = _find_chinese_font()

    def _load_font(size):
        from PIL import ImageFont
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    # ── Layer 1: Background ───────────────────────────────────────────────────
    bg_img = Image.new("RGBA", (W, H), (250, 250, 250, 255))
    bg_draw = ImageDraw.Draw(bg_img)
    for y in range(180):
        r = int(26 + (y / 180) * 10)
        g = int(26 + (y / 180) * 5)
        b = int(46 + (y / 180) * 20)
        bg_draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # ── Layer 2: Brand header text ─────────────────────────────────────────────
    header_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    header_draw = ImageDraw.Draw(header_img)
    font_large = _load_font(64)
    font_small = _load_font(24)
    header_draw.text((80, 50), brand_name or "品牌", font=font_large, fill=(255, 255, 255, 255))
    header_draw.text((80, 130), "Brand Visual Identity System", font=font_small, fill=(170, 170, 204, 255))

    # ── Layer 3: Color palette ─────────────────────────────────────────────────
    palette_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    palette_draw = ImageDraw.Draw(palette_img)
    font_medium = _load_font(36)
    palette_draw.rectangle([(0, 180), (W, 181)], fill=(224, 224, 224, 255))
    palette_draw.text((80, 210), "品牌色彩系统", font=font_medium, fill=(26, 26, 46, 255))

    swatch_y = 270
    swatch_w = 300
    swatch_h = 200
    gap = 30
    color_roles = ["主色调", "辅助色1", "辅助色2", "点缀色", "背景色"]
    for i, (color, role) in enumerate(zip(brand_colors[:5], color_roles)):
        x = 80 + i * (swatch_w + gap)
        h_color = tuple(int(color.lstrip("#")[j:j+2], 16) for j in (0, 2, 4))
        palette_draw.rectangle([(x, swatch_y), (x + swatch_w, swatch_y + swatch_h)],
                                fill=(*h_color, 255))
        label_bg = (255, 255, 255, 255) if _is_dark(color) else (51, 51, 51, 255)
        label_fg = (51, 51, 51, 255) if _is_dark(color) else (255, 255, 255, 255)
        palette_draw.rectangle([(x, swatch_y + swatch_h), (x + swatch_w, swatch_y + swatch_h + 50)],
                                fill=label_bg)
        palette_draw.text((x + 10, swatch_y + swatch_h + 10), color.upper(), font=font_small, fill=label_fg)
        palette_draw.text((x + 10, swatch_y + swatch_h + 60), role, font=font_small,
                           fill=(102, 102, 102, 255))

    # ── Layer 4: Logo (AI generated or placeholder) ────────────────────────────
    logo_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    logo_draw = ImageDraw.Draw(logo_img)
    lx, ly, lw, lh = 80, 580, 400, 300
    if logo_image is not None:
        # Composite AI-generated logo into the slot
        ai_logo = logo_image.convert("RGBA").resize((lw, lh), Image.LANCZOS)
        logo_img.paste(ai_logo, (lx, ly), ai_logo)
    else:
        logo_draw.rectangle([(lx, ly), (lx + lw, ly + lh)],
                             outline=(204, 204, 204, 255), width=3, fill=(240, 240, 240, 200))
        logo_draw.text((lx + 120, ly + 100), "LOGO", font=_load_font(72), fill=(187, 187, 187, 255))
        logo_draw.text((lx + 80, ly + 200), "设计概念区  可替换", font=font_small, fill=(170, 170, 170, 255))

    # ── Layer 5: Typography reference ─────────────────────────────────────────
    typo_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    typo_draw = ImageDraw.Draw(typo_img)
    tx = 560
    typo_draw.text((tx, 580), "字体规范", font=font_medium, fill=(26, 26, 46, 255))
    typo_draw.text((tx, 640), brand_name or "品牌名称", font=_load_font(64), fill=(26, 26, 46, 255))
    typo_draw.text((tx, 730), "Aa Bb Cc — 主标题字体", font=font_medium, fill=(51, 51, 51, 255))
    typo_draw.text((tx, 790), "品牌核心价值主张", font=font_small, fill=(102, 102, 102, 255))
    typo_draw.text((tx, 840), "Brand Core Value Proposition", font=font_small, fill=(153, 153, 153, 255))

    # ── Layer 6: Footer ────────────────────────────────────────────────────────
    footer_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    footer_draw = ImageDraw.Draw(footer_img)
    footer_draw.rectangle([(0, H - 60), (W, H)], fill=(26, 26, 46, 255))
    ts = datetime.now().strftime("%Y-%m-%d")
    footer_draw.text((80, H - 42),
                      f"Generated by Blank_WEB · {ts} · AI Brand Strategy Platform",
                      font=font_small, fill=(170, 170, 204, 255))

    # ── Assemble PSD with named layers ────────────────────────────────────────
    # Layers are inserted top-to-bottom (last inserted = topmost in PS)
    psd = PSDImage.new("RGBA", (W, H))

    layers_data = [
        (bg_img,      "Background"),
        (header_img,  "Brand Header"),
        (palette_img, "Color Palette"),
        (logo_img,    "Logo Placeholder"),
        (typo_img,    "Typography"),
        (footer_img,  "Footer"),
    ]

    for pil_img, layer_name in layers_data:
        layer = psd.create_pixel_layer(pil_img, name=layer_name)
        psd.append(layer)

    psd.save(file_path)
    return file_path, file_name


# ─────────────────────────────────────────────
# Shared rendering helper
# ─────────────────────────────────────────────

def _render_brand_visual(brand_name: str, content: str, logo_image=None):
    """Render the brand visual guide as a PIL Image (RGBA)."""
    from PIL import Image, ImageDraw, ImageFont

    hex_colors = re.findall(r'#([A-Fa-f0-9]{6})', content)
    brand_colors = ["#" + c for c in hex_colors[:5]] if hex_colors else [
        "#1a1a2e", "#16213e", "#0f3460", "#e94560", "#f5f5f5"
    ]
    while len(brand_colors) < 5:
        brand_colors.append("#cccccc")

    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "#fafafa")
    draw = ImageDraw.Draw(img)

    for y in range(180):
        r = int(26 + (y / 180) * 10)
        g = int(26 + (y / 180) * 5)
        b = int(46 + (y / 180) * 20)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    font_path = _find_chinese_font()
    font_large = font_medium = font_small = ImageFont.load_default()
    if font_path:
        try:
            font_large = ImageFont.truetype(font_path, 64)
            font_medium = ImageFont.truetype(font_path, 36)
            font_small = ImageFont.truetype(font_path, 24)
        except Exception:
            pass

    draw.text((80, 50), brand_name or "品牌", font=font_large, fill="#ffffff")
    draw.text((80, 130), "Brand Visual Identity System", font=font_small, fill="#aaaacc")
    draw.rectangle([(0, 180), (W, 181)], fill="#e0e0e0")
    draw.text((80, 210), "品牌色彩系统", font=font_medium, fill="#1a1a2e")

    swatch_y, swatch_w, swatch_h, gap = 270, 300, 200, 30
    color_roles = ["主色调", "辅助色1", "辅助色2", "点缀色", "背景色"]
    for i, (color, role) in enumerate(zip(brand_colors[:5], color_roles)):
        x = 80 + i * (swatch_w + gap)
        draw.rectangle([(x, swatch_y), (x + swatch_w, swatch_y + swatch_h)], fill=color)
        label_bg = "#ffffff" if _is_dark(color) else "#333333"
        label_fg = "#333333" if _is_dark(color) else "#ffffff"
        draw.rectangle([(x, swatch_y + swatch_h), (x + swatch_w, swatch_y + swatch_h + 50)], fill=label_bg)
        draw.text((x + 10, swatch_y + swatch_h + 10), color.upper(), font=font_small, fill=label_fg)
        draw.text((x + 10, swatch_y + swatch_h + 60), role, font=font_small, fill="#666666")

    lx, ly, lw, lh = 80, 580, 400, 300
    if logo_image is not None:
        ai_logo = logo_image.convert("RGB").resize((lw, lh), Image.LANCZOS)
        img.paste(ai_logo, (lx, ly))
    else:
        draw.rectangle([(lx, ly), (lx + lw, ly + lh)], outline="#cccccc", width=2, fill="#f0f0f0")
        draw.text((lx + 120, ly + 120), "LOGO", font=font_large, fill="#bbbbbb")
        draw.text((lx + 100, ly + 210), "设计概念区", font=font_small, fill="#aaaaaa")

    tx = 560
    draw.text((tx, 580), "字体规范", font=font_medium, fill="#1a1a2e")
    draw.text((tx, 640), brand_name or "品牌名称", font=font_large, fill="#1a1a2e")
    draw.text((tx, 730), "Aa Bb Cc — 主标题字体", font=font_medium, fill="#333333")
    draw.text((tx, 790), "品牌核心价值主张", font=font_small, fill="#666666")
    draw.text((tx, 840), "Brand Core Value Proposition", font=font_small, fill="#999999")

    draw.rectangle([(0, H - 60), (W, H)], fill="#1a1a2e")
    ts = datetime.now().strftime("%Y-%m-%d")
    draw.text((80, H - 42),
               f"Generated by Blank_WEB · {ts} · AI Brand Strategy Platform",
               font=font_small, fill="#aaaacc")

    return img, draw


def _is_dark(hex_color: str) -> bool:
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5
    except Exception:
        return True
