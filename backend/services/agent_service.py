from typing import AsyncGenerator, List, Optional
from sqlalchemy.orm import Session
from services.llm_service import LLMService, get_llm_config_for_agent
from services.seed_knowledge import ENHANCED_PROMPTS

llm_service = LLMService()

AGENT_META = {
    "strategy": {
        "name": "战略规划专家",
        "icon": "🎯",
        "system_prompt": ENHANCED_PROMPTS["strategy"],
    },
    "brand": {
        "name": "品牌设计专家",
        "icon": "🎨",
        "system_prompt": ENHANCED_PROMPTS["brand"],
    },
    "logo_design": {
        "name": "Logo设计专家",
        "icon": "✨",
        "system_prompt": "",  # Logo agent doesn't use LLM streaming — handled in main.py
    },
    "operations": {
        "name": "运营实施专家",
        "icon": "🚀",
        "system_prompt": ENHANCED_PROMPTS["operations"],
    },
    "poster_design": {
        "name": "海报设计专家",
        "icon": "🖼️",
        "system_prompt": "",  # Poster agent — AI image pipeline, handled in main.py
    },
}


def build_system_prompt(agent_type: str, knowledge_items: list, query: str = "", brand_name: str = "") -> str:
    base_prompt = AGENT_META[agent_type]["system_prompt"]

    # Build knowledge context from retrieved items
    knowledge_context = ""
    if knowledge_items:
        parts = []
        for item in knowledge_items:
            parts.append(f"### {item.title}\n{item.content}")
        knowledge_context = "\n\n".join(parts)

    # Fill template placeholders used in ENHANCED_PROMPTS (CRISPY framework)
    prompt = base_prompt.replace("{retrieved_knowledge_context}", knowledge_context or "（暂无相关知识库条目）")
    prompt = prompt.replace("{task_description}", query or "")
    prompt = prompt.replace("{brand_context}", brand_name or "（待定）")

    return prompt


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

    system_prompt = build_system_prompt(agent_type, knowledge_items, query=query, brand_name=brand_name)

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
    # Ordered pipeline (logo_design is handled separately in main.py)
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
