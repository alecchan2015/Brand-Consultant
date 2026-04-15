"""
AI-powered PPT slide structure generator.

Calls the LLM to transform long-form strategic content into a structured
JSON slide deck that pptx_service.py renders into a professional PPTX.
Falls back gracefully if LLM is unavailable.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior McKinsey & Company partner and expert PowerPoint designer.
Your task: transform strategic analysis content into a professional slide deck JSON.

DESIGN PRINCIPLES (Pyramid Principle + BCG/McKinsey visual storytelling):
- One clear message per slide — conclusion first, evidence second
- Bullet points: ≤ 15 Chinese characters, start with action verb or key finding
- Use real data / numbers; if not given, estimate with industry benchmarks
- MAXIMIZE visual slides (charts, matrices, timelines, flowcharts, metrics)
  over plain text. Aim for ≥60% of content slides to be visual/structured.
- Every content slide must carry an insight — no filler, no generic fluff
- When the source mentions processes with decisions or branches, ALWAYS
  render them as `flowchart` (with diamond decision nodes), never plain text
- When numbers appear (market size, growth, share, NPS, …), ALWAYS surface
  them in a `bar_chart` or `metrics` slide — do not bury them in bullets

OUTPUT: Return ONLY valid JSON — no markdown fences, no explanation, no commentary."""

# ── Slide schema prompt ────────────────────────────────────────────────────────
SLIDE_SCHEMA = """Return a JSON object:
{
  "title": "演示文稿完整标题",
  "subtitle": "副标题 / 定位语",
  "slides": [

    // ① Cover (always first)
    {"type":"cover","title":"...","subtitle":"..."},

    // ② Agenda
    {"type":"agenda","title":"报告结构","items":["第一部分: 市场分析","第二部分: ..."]},

    // ③ Executive summary
    {"type":"executive_summary","title":"执行摘要",
     "headline":"一句话核心结论（≤25字）",
     "points":["关键发现1","关键发现2","关键发现3"]},

    // ④ Section divider  (use before each major section)
    {"type":"section_divider","number":"01","title":"章节标题","subtitle":"简短说明"},

    // ⑤ Standard content bullets
    {"type":"content","title":"幻灯片标题","subtitle":"可选副标题",
     "bullets":["要点1（≤15字）","要点2","要点3","要点4"]},

    // ⑥ Two-column comparison
    {"type":"two_column","title":"对比标题",
     "left":{"title":"左侧标题","bullets":["...","..."]}
     "right":{"title":"右侧标题","bullets":["...","..."]}},

    // ⑦ SWOT
    {"type":"swot","title":"SWOT战略分析",
     "S":["优势1","优势2","优势3"],
     "W":["劣势1","劣势2"],
     "O":["机会1","机会2","机会3"],
     "T":["威胁1","威胁2"]},

    // ⑧ Bar / column chart  (use real or estimated numbers)
    {"type":"bar_chart","title":"图表标题","subtitle":"数据来源说明",
     "categories":["类别A","类别B","类别C","类别D"],
     "values":[35,52,28,45],"unit":"%"},

    // ⑨ Timeline / roadmap
    {"type":"timeline","title":"战略实施路线图",
     "phases":[
       {"period":"2024 Q1-Q2","title":"基础建设期","items":["行动1","行动2"]},
       {"period":"2024 Q3-Q4","title":"快速扩张期","items":["行动3","行动4"]},
       {"period":"2025","title":"规模化期","items":["行动5"]}
     ]},

    // ⑩ Process flow  (3-6 steps)
    {"type":"process","title":"核心流程",
     "steps":[
       {"title":"步骤1","desc":"简短描述（≤15字）"},
       {"title":"步骤2","desc":"简短描述"}
     ]},

    // ⑪ KPI metrics dashboard
    {"type":"metrics","title":"关键绩效指标",
     "items":[
       {"label":"市场占有率","value":"15","unit":"%","desc":"三年目标"},
       {"label":"年收入目标","value":"2000","unit":"万元","desc":"第二年"},
       {"label":"渠道覆盖","value":"50","unit":"城市","desc":"全国布局"},
       {"label":"客户满意度","value":"90","unit":"分","desc":"NPS目标"}
     ]},

    // ⑫ 2×2 Matrix (BCG / Ansoff / etc.)
    {"type":"matrix_2x2","title":"战略矩阵分析",
     "x_axis":"市场增长率","y_axis":"相对市场份额",
     "quadrants":[
       {"pos":"TL","title":"明星产品","items":["产品A","产品B"]},
       {"pos":"TR","title":"问题产品","items":["产品C"]},
       {"pos":"BL","title":"现金牛","items":["产品D"]},
       {"pos":"BR","title":"瘦狗产品","items":["产品E"]}
     ]},

    // ⑬ Flowchart (proper shapes: oval=start/end, rect=process, diamond=decision)
    {"type":"flowchart","title":"核心业务流程",
     "nodes":[
       {"shape":"oval",    "text":"开始"},
       {"shape":"rect",    "text":"市场调研", "desc":"收集用户需求与竞品数据"},
       {"shape":"rect",    "text":"方案制定", "desc":"制定品牌策略"},
       {"shape":"diamond", "text":"方案审批?", "yes":"通过", "no":"修订"},
       {"shape":"rect",    "text":"执行推进", "desc":"全面落地实施"},
       {"shape":"oval",    "text":"完成"}
     ]},

    // ⑭ Visual content (left=bullets, right=big icon + stat card)
    {"type":"visual_content","title":"核心数据洞察",
     "icon":"📊","stat":"85%","stat_label":"目标市场覆盖率",
     "bullets":["关键洞察1","关键洞察2","关键洞察3"],
     "right_bullets":["支撑数据1","支撑数据2"]},

    // ⑮ Closing (always last)
    {"type":"closing","title":"结论与下一步行动",
     "headline":"核心建议一句话",
     "points":["立即行动1","立即行动2","立即行动3"]}
  ]
}

REQUIREMENTS:
- Total: 16-20 slides
- Must include: cover, agenda, executive_summary, ≥2 section_dividers, closing
- Must include AT LEAST TWO of: swot, bar_chart, metrics, matrix_2x2
- Must include AT LEAST ONE: flowchart  (use diamond for any decision node)
- Must include AT LEAST ONE: visual_content  (big icon + stat card)
- Must include AT LEAST ONE: timeline  (roadmap of the implementation)
- Prefer charts over bullets when numbers exist; prefer matrix_2x2 over
  two_column when the comparison has two real axes
- All text in Chinese (framework names like SWOT/BCG/KPI may stay English)
- Bullet / item text: concise, action-oriented, ≤15 characters
- Chart values: REAL numbers from the source, or industry-benchmark estimates —
  never placeholders like "待定" / "TBD"
- Use flowchart (not process) when there are decisions/branches in the flow
- Do NOT repeat the same slide layout back-to-back; interleave visuals

CONTENT HINTS (optional, inline markers inside bullet text will be parsed):
  [CHART: bar|pie|line, 说明]   → hints the renderer to upgrade to a chart
  [IMAGE: 简短描述]             → hints a visual emphasis block
Use these sparingly and only when a concrete data point exists.
"""


async def generate_slide_structure(
    brand_name: str,
    content: str,
    agent_type: str,
    db: Session,
) -> Optional[Dict[str, Any]]:
    """
    Call LLM to produce a structured JSON slide deck.
    Returns None on any failure so the caller can use the markdown fallback.
    """
    try:
        from openai import AsyncOpenAI
        from models import LLMConfig

        # Prefer agent-specific config, fall back to any active non-image config
        config = (
            db.query(LLMConfig)
            .filter(LLMConfig.agent_type == agent_type, LLMConfig.is_active == True)
            .first()
        )
        if not config:
            config = (
                db.query(LLMConfig)
                .filter(LLMConfig.is_active == True)
                .filter(~LLMConfig.agent_type.in_(["image_gen"]))
                .first()
            )
        if not config:
            print("[PPTXAgent] No LLM config found")
            return None

        client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or None,
            timeout=120,
        )

        agent_label = {
            "strategy": "战略规划专家",
            "brand":    "品牌设计专家",
            "operations": "运营实施专家",
        }.get(agent_type, agent_type)

        user_prompt = (
            f"品牌名称: {brand_name}\n"
            f"专家角色: {agent_label}\n\n"
            f"以下是原始分析内容（请提炼关键信息，切勿照搬原文）:\n"
            f"---\n{content[:7000]}\n---\n\n"
            f"{SLIDE_SCHEMA}\n\n"
            "⚠️ 图表数值若内容未明确给出，请根据行业经验合理估算。\n"
            "⚠️ 确保输出为合法 JSON，可被 json.loads() 直接解析。"
        )

        resp = await client.chat.completions.create(
            model=config.model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )

        raw = resp.choices[0].message.content.strip()
        # Strip accidental markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$",       "", raw).strip()

        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            print("[PPTXAgent] No JSON object found in response")
            return None

        data = json.loads(m.group())
        slides = data.get("slides", [])
        if len(slides) < 5:
            print(f"[PPTXAgent] Too few slides ({len(slides)}), rejecting")
            return None

        print(f"[PPTXAgent] ✓ Generated {len(slides)} slides via AI")
        return data

    except Exception as exc:
        print(f"[PPTXAgent] ✗ {exc}")
        return None
