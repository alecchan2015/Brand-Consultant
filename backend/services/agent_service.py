from typing import AsyncGenerator, List, Optional
from sqlalchemy.orm import Session
from services.llm_service import LLMService, get_llm_config_for_agent

llm_service = LLMService()

AGENT_META = {
    "strategy": {
        "name": "战略规划专家",
        "icon": "🎯",
        "system_prompt": """你是一位拥有20年以上经验的家具品牌战略顾问，曾服务宜家、红星美凯龙、顾家家居等头部品牌。

你专注于以下核心领域：
1. 市场分析与定位：目标市场细分、消费者画像、竞争格局分析
2. 品牌战略定位：差异化优势、价值主张、品牌主张与核心理念
3. 增长战略：市场拓展路径、产品线规划、渠道策略
4. 竞争策略：蓝海/红海分析、差异化竞争路径
5. 品牌资产建立：长期品牌价值与护城河构建

【输出要求】
请以专业顾问报告格式输出，使用Markdown，包含以下章节：
## 执行摘要
## 市场环境分析
## 目标消费者画像
## 战略定位
## 核心竞争策略
## 品牌价值主张
## 短中长期战略路径

语言：中文，专业严谨，数据驱动，可操作性强。""",
    },
    "brand": {
        "name": "品牌设计专家",
        "icon": "🎨",
        "system_prompt": """你是一位专注于家具行业的资深品牌创意总监，曾主导多个知名家具品牌的视觉体系建立。

你的专长包括：
1. 品牌视觉系统：Logo设计理念与规范、视觉语言体系
2. 色彩策略：主色调、辅助色、情感色彩及应用规范
3. 字体体系：中英文主字体、辅助字体、层级规范
4. 视觉物料清单：包装、门店、宣传物料设计指引
5. 品牌调性：高端/亲民/现代/传统/北欧/中式等风格定义

【输出要求】
请以品牌手册格式输出，使用Markdown，包含：
## 品牌核心理念
## Logo设计概念与说明
## 主视觉色彩方案（提供Hex色值）
## 字体规范
## 视觉风格指引
## 物料设计规范清单
## 品牌禁止事项

语言：中文，专业细致，设计参数明确（色值、尺寸等）。""",
    },
    "operations": {
        "name": "运营实施专家",
        "icon": "🚀",
        "system_prompt": """你是一位资深家具品牌运营专家，拥有15年以上品牌从0到1孵化及规模化运营经验。

你的专长包括：
1. 渠道建设：线上（天猫/京东/抖音）线下（直营/加盟）渠道规划
2. 内容营销：品牌故事、内容矩阵、KOL/KOC合作策略
3. 零售运营：门店选址、体验设计、转化率优化
4. 数字化运营：电商运营、私域流量、会员体系、CRM
5. 组织建设：团队架构、KPI体系、预算规划

【输出要求】
请以执行计划格式输出，使用Markdown，包含：
## 年度运营战略
## 渠道矩阵建设方案
## 内容营销计划
## 关键里程碑（附时间表）
## 预算框架建议
## KPI指标体系
## 风险与应对措施

语言：中文，详细可执行，含时间节点和资源需求。""",
    },
}


def build_system_prompt(agent_type: str, knowledge_items: list) -> str:
    base_prompt = AGENT_META[agent_type]["system_prompt"]
    if knowledge_items:
        knowledge_text = "\n\n【经验知识库】\n以下是相关领域的专业知识和案例，请参考：\n"
        for item in knowledge_items:
            knowledge_text += f"\n### {item.title}\n{item.content}\n"
        return base_prompt + knowledge_text
    return base_prompt


async def run_agent(
    agent_type: str,
    query: str,
    brand_name: str,
    context: str,
    db: Session,
    user_id: int = None,
    task_id: int = None,
) -> AsyncGenerator[str, None]:
    """Run a single agent and stream its output"""
    from models import AgentKnowledge

    # Get knowledge base
    knowledge_items = db.query(AgentKnowledge).filter(
        AgentKnowledge.agent_type == agent_type,
        AgentKnowledge.is_active == True
    ).limit(5).all()

    system_prompt = build_system_prompt(agent_type, knowledge_items)

    # Build user message
    user_content = f"品牌名称：{brand_name or '（待定）'}\n\n用户需求：{query}"
    if context:
        user_content = f"{user_content}\n\n【前序分析参考】\n{context}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # Get LLM config
    config = get_llm_config_for_agent(agent_type, db)
    if not config:
        yield "⚠️ 该Agent尚未配置大模型，请联系管理员在后台配置LLM。"
        return

    async for chunk in llm_service.stream_chat(
        messages=messages,
        provider=config.provider,
        api_key=config.api_key,
        model_name=config.model_name,
        base_url=config.base_url,
        db=db,
        user_id=user_id,
        task_id=task_id,
        agent_type=agent_type,
    ):
        yield chunk


async def run_multi_agent(
    agents: List[str],
    query: str,
    brand_name: str,
    db: Session,
    user_id: int = None,
    task_id: int = None,
) -> AsyncGenerator[dict, None]:
    """
    Orchestrate multiple agents sequentially.
    Each agent gets the output of previous agents as context.
    Yields SSE-style dicts: {type, agent, content}
    """
    # Ordered pipeline
    pipeline = [a for a in ["strategy", "brand", "operations"] if a in agents]
    accumulated_context = {}

    for agent_type in pipeline:
        meta = AGENT_META[agent_type]
        yield {"type": "agent_start", "agent": agent_type, "name": meta["name"]}

        context_parts = []
        if "strategy" in accumulated_context and agent_type in ("brand", "operations"):
            context_parts.append(f"=== 战略规划专家输出 ===\n{accumulated_context['strategy']}")
        if "brand" in accumulated_context and agent_type == "operations":
            context_parts.append(f"=== 品牌设计专家输出 ===\n{accumulated_context['brand']}")

        context = "\n\n".join(context_parts)
        full_content = []

        async for chunk in run_agent(
            agent_type, query, brand_name, context, db,
            user_id=user_id, task_id=task_id,
        ):
            full_content.append(chunk)
            yield {"type": "chunk", "agent": agent_type, "content": chunk}

        accumulated_context[agent_type] = "".join(full_content)
        yield {"type": "agent_done", "agent": agent_type, "full_content": accumulated_context[agent_type]}
