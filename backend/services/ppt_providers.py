"""
Multi-provider PPTX generation layer.

Inspired by the CahayaBeauty PPT Feature Engineering Guide v2.0 — adapts the
Provider Pattern + Fallback chain to this Python/FastAPI stack.

Providers (strategy pattern):
    - LocalPPTXProvider     → python-pptx renderer (services.pptx_service)
    - GammaProvider         → Gamma public API (https://public-api.gamma.app)
    - PresentonProvider     → self-hosted Presenton instance

Primary provider is selected via env `PPT_PROVIDER` (local|gamma|presenton);
unknown / unconfigured providers automatically fall back to `local` so the
platform never fails to deliver a deck.

Env vars:
    PPT_PROVIDER          primary provider name (default: local)
    PPT_FALLBACK          fallback provider name (default: local)
    GAMMA_API_KEY         Gamma API key
    GAMMA_THEME_ID        optional theme id
    PRESENTON_ENDPOINT    Presenton base URL (default http://localhost:5000)

Every provider returns the resolved PPTX file at `file_path` and the same
(file_path, file_name) contract so the caller is provider-agnostic.
"""
from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


# ── Abstract base ──────────────────────────────────────────────────────────────
class BasePPTProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        *,
        task_id: int,
        agent_type: str,
        brand_name: str,
        content: str,
        file_path: str,
        db=None,
    ) -> str:
        """Produce a .pptx file at `file_path` and return the path."""

    # Convenience: pretty label for logs
    def __repr__(self) -> str:
        return f"<PPTProvider {self.name}>"


# ── Local python-pptx (always available) ──────────────────────────────────────
class LocalPPTXProvider(BasePPTProvider):
    name = "local"

    async def generate(self, *, task_id, agent_type, brand_name, content,
                       file_path, db=None) -> str:
        from services.pptx_service import generate_pptx
        await generate_pptx(task_id, agent_type, brand_name, content,
                            file_path, db=db)
        return file_path


# ── Gamma API adapter ─────────────────────────────────────────────────────────
class GammaProvider(BasePPTProvider):
    """
    Submits markdown content to Gamma's public API, polls until the PPTX
    export is ready, and downloads it to `file_path`.

    Endpoint / schema cross-checked against the `statechangelabs/gamma-app-mcp`
    reference implementation (v0.2 public API, 300s poll budget).
    """
    name = "gamma"
    # Gamma public API — v0.2 was sunset 2026; v1.0 is the current stable
    BASE = "https://public-api.gamma.app/v1.0"

    AGENT_INSTRUCTIONS = {
        "strategy":   "以麦肯锡战略顾问的口吻撰写，金字塔原理，结论先行，每页一个核心洞察，多用数据与图表。",
        "brand":      "以资深品牌设计师的视角，强调视觉调性、品牌故事、情绪价值，配色与意象描述具体。",
        "operations": "以运营实施专家的角度，给出可执行的行动项、时间节点与里程碑，流程化、可落地。",
    }

    def __init__(
        self,
        api_key: str,
        theme_name: Optional[str] = None,
        num_cards: int = 16,
    ):
        self.api_key = api_key
        self.theme_name = theme_name
        self.num_cards = max(1, min(60, num_cards))

    async def generate(self, *, task_id, agent_type, brand_name, content,
                       file_path, db=None) -> str:
        import httpx

        # v1.0 API uses x-api-key header (not Authorization: Bearer)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        body = {
            "inputText":              f"# {brand_name}\n\n{content[:9000]}",
            "textMode":               "generate",
            "numCards":               self.num_cards,
            "cardSplit":              "auto",
            "additionalInstructions": self.AGENT_INSTRUCTIONS.get(
                agent_type, "撰写一份专业的商业策划演示文稿。"
            ),
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.BASE}/generations",
                                  headers=headers, json=body)
            if r.status_code >= 400:
                raise RuntimeError(
                    f"Gamma submit failed [{r.status_code}]: {r.text[:500]}"
                )
            gen_id = r.json().get("generationId")
            if not gen_id:
                raise RuntimeError(f"Gamma response missing generationId: {r.text[:500]}")

            # Poll every 5s up to 300s
            poll_client = httpx.AsyncClient(timeout=30)
            gamma_url: Optional[str] = None
            pptx_url: Optional[str] = None
            try:
                for _ in range(60):
                    await asyncio.sleep(5)
                    p = await poll_client.get(
                        f"{self.BASE}/generations/{gen_id}", headers=headers
                    )
                    if p.status_code >= 400:
                        continue
                    data = p.json()
                    status = (data.get("status") or "").lower()
                    if status in ("completed", "complete"):
                        # v1.0 API returns gammaUrl (web page); pptxExportUrl
                        # may appear in future API versions
                        pptx_url  = data.get("pptxExportUrl") or data.get("exportUrl")
                        gamma_url = data.get("gammaUrl")
                        break
                    if status == "failed":
                        raise RuntimeError(
                            f"Gamma generation failed: {data.get('error') or data}"
                        )
            finally:
                await poll_client.aclose()

            if not gamma_url and not pptx_url:
                raise RuntimeError("Gamma generation timed out (>300s)")

            if pptx_url:
                # Direct PPTX download (future API versions)
                dl = await httpx.AsyncClient(timeout=60).get(pptx_url)
                dl.raise_for_status()
                Path(file_path).write_bytes(dl.content)
                print(f"[Gamma] PPTX downloaded from {pptx_url}")
            else:
                # v1.0 only provides a web URL — fall back to local PPTX renderer
                # but embed the gamma_url as a reference slide
                print(f"[Gamma] generation complete → {gamma_url}")
                print("[Gamma] v1.0 API has no PPTX download; falling back to local renderer")
                enhanced_content = (
                    f"{content}\n\n---\n"
                    f"> 📎 本演示文稿已同步生成 Gamma 在线版本：{gamma_url}"
                )
                from services.pptx_service import generate_pptx
                await generate_pptx(task_id, agent_type, brand_name,
                                    enhanced_content, file_path, db=db)

        return file_path


# ── Presenton adapter ─────────────────────────────────────────────────────────
class PresentonProvider(BasePPTProvider):
    """
    Calls a self-hosted Presenton instance. BYOK, unlimited parallel — a
    good private-cloud fallback (see guide §3.5).
    """
    name = "presenton"

    def __init__(self, endpoint: str = "http://localhost:5000"):
        self.endpoint = endpoint.rstrip("/")

    async def generate(self, *, task_id, agent_type, brand_name, content,
                       file_path, db=None) -> str:
        import httpx

        payload = {
            "content":   f"# {brand_name}\n\n{content[:7000]}",
            "n_slides":  16,
            "language":  "Chinese",
            "template":  "business",
            "export_as": "pptx",
        }
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.endpoint}/api/v1/ppt/presentation/generate",
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            rel = data.get("path") or data.get("url")
            if not rel:
                raise RuntimeError("Presenton returned no file path")
            url = rel if rel.startswith("http") else f"{self.endpoint}{rel}"
            dl = await client.get(url, timeout=60)
            dl.raise_for_status()
            Path(file_path).write_bytes(dl.content)
        return file_path


# ── Factory + fallback chain ──────────────────────────────────────────────────
def _build(name: str, cfg: dict) -> Optional[BasePPTProvider]:
    name = (name or "").strip().lower()
    if name in ("", "local", "python-pptx", "pptx"):
        return LocalPPTXProvider()
    if name == "gamma":
        key = (cfg.get("gamma_api_key") or "").strip()
        if not key:
            print("[PPTProvider] gamma_api_key missing — cannot build gamma")
            return None
        # Accept both the legacy 'gamma_theme_id' key and the new
        # 'gamma_theme_name' for backward compatibility.
        theme = (cfg.get("gamma_theme_name")
                 or cfg.get("gamma_theme_id")
                 or None) or None
        try:
            num_cards = int(cfg.get("gamma_num_cards") or 16)
        except (TypeError, ValueError):
            num_cards = 16
        return GammaProvider(api_key=key, theme_name=theme, num_cards=num_cards)
    if name == "presenton":
        return PresentonProvider(
            endpoint=cfg.get("presenton_endpoint") or "http://localhost:5000"
        )
    print(f"[PPTProvider] Unknown provider '{name}'")
    return None


async def generate_via_providers(
    *,
    task_id: int,
    agent_type: str,
    brand_name: str,
    content: str,
    file_path: str,
    db=None,
) -> tuple[str, str]:
    """
    Try primary provider, then fallback, then hard-fall-back to local.
    Config is loaded from the DB (system_settings.ppt_provider_config), with
    env vars as the deployment-time default. Returns the path + provider name.
    """
    from services.ppt_settings import load_config
    cfg = load_config(db)
    primary_name  = cfg.get("provider") or "local"
    fallback_name = cfg.get("fallback") or "local"

    chain = []
    for nm in (primary_name, fallback_name, "local"):
        p = _build(nm, cfg)
        if p and not any(existing.name == p.name for existing in chain):
            chain.append(p)

    last_err: Optional[Exception] = None
    for provider in chain:
        try:
            print(f"[PPTProvider] → trying {provider.name}")
            await provider.generate(
                task_id=task_id,
                agent_type=agent_type,
                brand_name=brand_name,
                content=content,
                file_path=file_path,
                db=db,
            )
            print(f"[PPTProvider] ✓ {provider.name} succeeded")
            return file_path, provider.name
        except Exception as exc:                       # noqa: BLE001
            print(f"[PPTProvider] ✗ {provider.name} failed: {exc}")
            last_err = exc

    raise RuntimeError(f"All PPT providers failed. Last error: {last_err}")


# ── Admin / debug: list + test ────────────────────────────────────────────────
def list_providers(db=None) -> list[dict]:
    """Return status of every provider (for an admin endpoint)."""
    from services.ppt_settings import load_config
    cfg = load_config(db)
    primary  = cfg.get("provider") or "local"
    fallback = cfg.get("fallback") or "local"

    def _role(n: str) -> str:
        if n == primary:  return "primary"
        if n == fallback: return "fallback"
        return "inactive"

    return [
        {
            "name":      "local",
            "label":     "python-pptx (本地渲染)",
            "available": True,
            "role":      _role("local"),
        },
        {
            "name":      "gamma",
            "label":     "Gamma API (高质量云端)",
            "available": bool((cfg.get("gamma_api_key") or "").strip()),
            "role":      _role("gamma"),
        },
        {
            "name":      "presenton",
            "label":     "Presenton (自托管)",
            "available": bool((cfg.get("presenton_endpoint") or "").strip()),
            "role":      _role("presenton"),
        },
    ]


async def test_provider(name: str, db=None) -> dict:
    """Ping a provider with a minimal request to verify connectivity."""
    from services.ppt_settings import load_config
    cfg = load_config(db)
    provider = _build(name, cfg)
    if not provider:
        return {"ok": False, "provider": name, "error": "provider not configured"}

    # For `local` we don't actually render — just report ready.
    if provider.name == "local":
        return {"ok": True, "provider": "local", "message": "python-pptx ready"}

    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
    tmp.close()
    try:
        await provider.generate(
            task_id=0,
            agent_type="strategy",
            brand_name="ConnTest",
            content="## Connectivity Test\n- ping",
            file_path=tmp.name,
            db=db,
        )
        size = os.path.getsize(tmp.name)
        return {"ok": True, "provider": provider.name, "file_size": size}
    except Exception as exc:                            # noqa: BLE001
        return {"ok": False, "provider": provider.name, "error": str(exc)}
    finally:
        try: os.unlink(tmp.name)
        except Exception: pass
