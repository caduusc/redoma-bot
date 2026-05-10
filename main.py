"""
Redoma Bot — Main.

Inicia o bot localmente. Abre o Chrome em standby e fica
monitorando mensagens novas no Supabase.

Fluxo:
  1. Abre o Chrome com perfil pessoal (standby)
  2. Consulta conversations open/unclaimed + mensagens com link
  3. Identifica marketplace na URL
  4. Claim: status='claimed', claimed_by='Bot Redoma'
  5. Gera link de afiliado (navega na plataforma)
  6. Insere resposta do bot no Supabase
  7. Se erro → direciona pra atendente humano + avisa no WhatsApp
  8. Volta pro passo 2

Uso:
    python main.py
"""

import asyncio
import logging
import re
import sys
import uuid
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

from modulos.supabase_func import (
    read_open_conversations,
    read_messages_with_links,
    insert_bot_response,
    update_conversation, read_community_by_id, get_affiliate_tag,
)
from modulos.playwright_func import (
    BrowserSession,
    navigate,
    human_delay,
    log_current_state,
)
from mktplaces.mercadolivre import gerar_link_mercadolivre
from mktplaces.amazon import gerar_link_amazon
from mktplaces.shopee import gerar_link_shopee

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Config
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

POLL_INTERVAL_SECONDS = 10       # Intervalo entre consultas ao Supabase
BOT_NAME = "Bot Redoma"
AGENT_NAME = "Atendente Redoma"

# Z-API (pra notificar atendente quando o bot não conseguir resolver)
ZAPI_INSTANCE_ID = ""   # preencher
ZAPI_TOKEN = ""         # preencher
ZAPI_CLIENT_TOKEN = ""  # preencher
AGENT_PHONES = ["5511978060056", "5511944774344"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("redoma.main")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Identificação de marketplace
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MARKETPLACE_PATTERNS = {
    "mercadolivre": [
        re.compile(r"https?://[^\s]*mercadolivre\.com\.br[^\s]*", re.IGNORECASE),
        re.compile(r"https?://meli\.la/[^\s]*", re.IGNORECASE),
    ],
    "shopee": [
        re.compile(r"https?://[^\s]*shopee\.com\.br[^\s]*", re.IGNORECASE),
        re.compile(r"https?://[^\s]*shp.ee\.com\.br[^\s]*", re.IGNORECASE),
    ],
    "amazon": [
        re.compile(r"https?://[^\s]*amazon\.com\.br[^\s]*", re.IGNORECASE),
        re.compile(r"https?://[^\s]*amzn\.[^\s]*", re.IGNORECASE),
    ],
    "magalu": [
        re.compile(r"https?://[^\s]*magazineluiza\.com\.br[^\s]*", re.IGNORECASE),
        re.compile(r"https?://[^\s]*magazinevoce\.com\.br[^\s]*", re.IGNORECASE),
    ],
}


def identify_marketplace(text: str) -> tuple[str | None, str | None]:
    """
    Identifica o marketplace e extrai a URL do produto.

    Returns:
        (marketplace, product_url) ou (None, None) se não identificar.
    """
    for marketplace, patterns in MARKETPLACE_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return marketplace, match.group(0).strip()

    return None, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Geração do link de afiliado
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def generate_affiliate_link(
    session: BrowserSession,
    marketplace: str,
    product_url: str,
    tag: str | None = None,
) -> dict:
    """
    Gera link de afiliado navegando na plataforma correspondente.

    Returns:
        {"success": bool, "affiliate_link": str | None, "error": str | None}
    """
    page = session.get_page()

    if marketplace == "mercadolivre":
        return await gerar_link_mercadolivre(page, product_url, tag)

    elif marketplace == "amazon":
        return await gerar_link_amazon(page, product_url, tag)

    elif marketplace == "shopee":
        return await gerar_link_shopee(page, product_url, tag)

    # ┌─────────────────────────────────────────────────────────────┐
    # │  TODO: Implementar navegação por marketplace               │
    # │                                                             │
    # │  Aqui entra a função específica de cada plataforma.        │
    # │  Cada uma vai:                                              │
    # │    1. Navegar pro painel de afiliados                       │
    # │    2. Colar a product_url                                   │
    # │    3. Clicar em gerar                                       │
    # │    4. Extrair o link gerado                                 │
    # │                                                             │
    # │  Exemplo de como vai ficar:                                 │
    # │                                                             │
    # │  if marketplace == "mercadolivre":                          │
    # │      return await gerar_link_mercadolivre(page, product_url)│
    # │  elif marketplace == "shopee":                              │
    # │      return await gerar_link_shopee(page, product_url)      │
    # │  elif marketplace == "amazon":                              │
    # │      return await gerar_link_amazon(page, product_url)      │
    # │  ...                                                        │
    # └─────────────────────────────────────────────────────────────┘

    logger.warning(f"Generator para '{marketplace}' ainda não implementado.")
    return {
        "success": False,
        "affiliate_link": None,
        "error": f"Generator '{marketplace}' não implementado.",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Notificação WhatsApp (Z-API)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def notify_agent_whatsapp(conversation_id: str, error_msg: str) -> None:
    """
    Avisa os atendentes via WhatsApp que o bot não conseguiu
    gerar o link e a conversa precisa de atendimento humano.
    """
    if not all([ZAPI_INSTANCE_ID, ZAPI_TOKEN, ZAPI_CLIENT_TOKEN]):
        logger.warning("Z-API não configurada — notificação não enviada.")
        return

    import httpx

    text = (
        f"Bot Redoma não conseguiu gerar o link.\n\n"
        f"Conversa: {conversation_id}\n"
        f"Motivo: {error_msg}\n\n"
        f"A conversa foi direcionada para atendimento humano."
    )

    url = (
        f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}"
        f"/token/{ZAPI_TOKEN}/send-text"
    )

    async with httpx.AsyncClient(timeout=15) as http:
        for phone in AGENT_PHONES:
            try:
                res = await http.post(
                    url,
                    json={"phone": phone, "message": text},
                    headers={
                        "Content-Type": "application/json",
                        "Client-Token": ZAPI_CLIENT_TOKEN,
                    },
                )
                if res.is_success:
                    logger.info(f"Atendente {phone[:8]}... notificado.")
                else:
                    logger.error(f"Z-API erro {res.status_code} para {phone[:8]}...")
            except Exception as e:
                logger.error(f"Falha ao notificar {phone[:8]}...: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Processamento de uma conversa
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_conversation(
    session: BrowserSession,
    conversation: dict,
    messages: list[dict],
) -> None:
    """
    Processa as mensagens com link de uma conversa.

    Pra cada mensagem com link identificável:
      1. Claim da conversa (Bot Redoma)
      2. Gera link de afiliado
      3. Insere resposta do bot
      4. Se erro → direciona pra atendente humano
    """
    conv_id = conversation["id"]

    for msg in messages:
        text = msg.get("text", "")
        msg_id = msg.get("id", "?")

        # Identifica marketplace
        marketplace, product_url = identify_marketplace(text)
        tag = get_affiliate_tag(conversation["community_id"], marketplace)

        if not marketplace or not product_url:
            # Sem link reconhecido → não toca, atendente cuida
            logger.debug(f"Msg {msg_id[:12]}... sem marketplace — ignorando.")
            continue

        logger.info(
            f"🔍 Msg {msg_id[:12]}... | "
            f"marketplace={marketplace} | url={product_url[:50]}..."
        )

        # ── 1. Claim da conversa ──
        update_conversation(
            conv_id,
            status="claimed",
            claimed_by=BOT_NAME,
            claimed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"Conversa {conv_id[:12]}... claimed pelo {BOT_NAME}.")


        # ── 2. Gera link de afiliado ──
        result = await generate_affiliate_link(session, marketplace, product_url, tag)

        if result["success"] and result["affiliate_link"]:
            # ── 3. Sucesso → insere resposta do bot ──
            affiliate_link = result["affiliate_link"]
            response_text = (
                f"Seu link está pronto! : {affiliate_link}"
                f"   - O link tem duração de 24 horas."
            )

            inserted = insert_bot_response(
                id=str(uuid.uuid4()),
                text=response_text,
                conversation_id=conv_id,
                client_token=msg.get("client_token"),
            )

            if inserted:
                logger.info(f"Resposta inserida: {inserted['id'][:12]}...")
            else:
                logger.error(f"Erro ao inserir resposta no banco.")

        else:
            # ── 4. Erro → direciona pra atendente humano ──
            error_msg = result.get("error", "Erro desconhecido")
            logger.warning(f"Falha na geração: {error_msg}")

            update_conversation(
                conv_id,
                claimed_by=AGENT_NAME,
            )
            logger.info(f"Conversa {conv_id[:12]}... direcionada para {AGENT_NAME}.")

            #await notify_agent_whatsapp(conv_id, error_msg)

        # Só processa o primeiro link da conversa
        # (evita gerar múltiplos links se o cliente mandou vários)
        break


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Loop principal
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def poll_and_process(session: BrowserSession) -> int:
    """
    Uma iteração do loop: consulta Supabase e processa o que encontrar.
    Retorna a quantidade de conversas processadas.
    """
    # Busca conversas abertas sem atendente
    conversations = read_open_conversations()
    if not conversations:
        return 0

    processed = 0

    for conv in conversations:
        conv_id = conv["id"]

        # Busca mensagens com link nessa conversa
        messages = read_messages_with_links(conv_id)
        if not messages:
            # Conversa sem link → pula, atendente humano cuida
            continue

        # Garante que o browser tá vivo antes de trabalhar
        await session.ensure_alive()

        await process_conversation(session, conv, messages)
        processed += 1

    return processed


async def main() -> None:
    """Entry point do bot."""
    print()
    print("=" * 60)
    print("Redoma Bot Atendimento — Online")
    print("=" * 60)
    print()
    print("Feche o Chrome antes de iniciar!")
    print()

    # ── Abre o Chrome com perfil pessoal ──
    session = BrowserSession()
    await session.start()

    logger.info(f"Bot rodando. Consultando a cada {POLL_INTERVAL_SECONDS}s.")
    logger.info("   Pressione Ctrl+C para encerrar.\n")

    try:
        while True:
            try:
                processed = await poll_and_process(session)

                if processed > 0:
                    logger.info(f"📊 {processed} conversa(s) processada(s) neste ciclo.")

            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Erro no ciclo: {e}", exc_info=True)

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print()
        logger.info("Encerrando bot...")

    finally:
        await session.stop()
        logger.info("Bot encerrado.")


if __name__ == "__main__":
    asyncio.run(main())