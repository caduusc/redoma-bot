"""
api.py — Redoma Bot · Serviço de geração de links de afiliado

Expõe o Playwright como um micro-serviço HTTP local.
O Next.js (Redoma v2) chama este serviço quando recebe uma URL de produto.

Uso:
    pip install fastapi uvicorn httpx playwright
    playwright install chromium
    python api.py

Endpoint principal:
    POST http://localhost:8001/generate-link
    Body: { "marketplace": "mercadolivre", "product_url": "..." }
    Response: { "success": true, "affiliate_link": "..." }
              { "success": false, "error": "..." }
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.stdout.reconfigure(encoding="utf-8")

from modulos.playwright_func import BrowserSession
from mktplaces.mercadolivre import gerar_link_mercadolivre
from mktplaces.amazon import gerar_link_amazon
from mktplaces.shopee import gerar_link_shopee

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("redoma.api")

# ─────────────────────────────────────────────────────────────────────
# Browser singleton
# ─────────────────────────────────────────────────────────────────────

browser_session: BrowserSession | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global browser_session
    logger.info("Iniciando browser (Chrome)...")
    browser_session = BrowserSession()
    await browser_session.start()
    logger.info("Browser pronto. API aguardando requisições.")
    yield
    logger.info("Encerrando browser...")
    if browser_session:
        await browser_session.stop()
    logger.info("API encerrada.")


# ─────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────

app = FastAPI(title="Redoma Affiliate Link Generator", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────

class GenerateLinkRequest(BaseModel):
    marketplace: str  # "mercadolivre" | "amazon" | "shopee" | "magalu"
    product_url: str  # URL original enviada pelo usuário


class GenerateLinkResponse(BaseModel):
    success: bool
    affiliate_link: str | None = None
    error: str | None = None


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "browser": "running" if browser_session else "not started"}


@app.post("/generate-link", response_model=GenerateLinkResponse)
async def generate_link(req: GenerateLinkRequest):
    if not browser_session:
        return GenerateLinkResponse(success=False, error="Browser não inicializado. Reinicie o serviço.")

    logger.info(f"→ generate-link | marketplace={req.marketplace} | url={req.product_url[:60]}...")

    # Cada marketplace tem seu próprio lock — marketplaces diferentes rodam
    # em paralelo, mas dois links do mesmo marketplace são serializados.
    async with browser_session.get_lock_for(req.marketplace):
        try:
            await browser_session.ensure_alive()
            page = await browser_session.get_page_for(req.marketplace)

            match req.marketplace:
                case "mercadolivre":
                    result = await gerar_link_mercadolivre(page, req.product_url)
                case "amazon":
                    result = await gerar_link_amazon(page, req.product_url)
                case "shopee":
                    result = await gerar_link_shopee(page, req.product_url)
                case _:
                    result = {
                        "success": False,
                        "affiliate_link": None,
                        "error": f"Marketplace '{req.marketplace}' não suportado.",
                    }

            if result["success"]:
                logger.info(f"✓ Link gerado: {result['affiliate_link'][:60]}...")
            else:
                logger.warning(f"✗ Falha: {result['error']}")

            return GenerateLinkResponse(**result)

        except Exception as e:
            logger.error(f"Erro inesperado: {e}", exc_info=True)
            return GenerateLinkResponse(success=False, error=f"Erro interno: {str(e)}")


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  Redoma Affiliate API — localhost:8001")
    print("  Feche o Chrome antes de iniciar!")
    print("=" * 60)
    print()
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False, log_level="warning")