"""
Redoma — Camada de acesso ao Supabase.

Funções de CRUD pras tabelas `conversations` e `messages`.
Sem lógica de negócio, sem bot, sem Z-API — só banco.

Uso:
    from supabase_client import (
        read_open_conversations,
        read_messages_with_links,
        insert_message,
        insert_bot_response,
    )
"""

import sys
import os
import json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

from config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client, Client

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Client singleton
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_client() -> Client:
    """Retorna a instância do client Supabase."""
    return _client


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEITURA — Conversations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def read_open_conversations(limit: int = 50) -> list[dict]:
    """
    Conversas abertas e não reivindicadas por atendente.
    Filtros: status='open', claimed_by IS NULL.
    """
    try:
        res = _client.table("conversations") \
            .select("*") \
            .eq("status", "open") \
            .is_("claimed_by", "null") \
            .order("created_at", desc=False) \
            .limit(limit) \
            .execute()
        return res.data or []
    except Exception as e:
        print(f"ERRO  read_open_conversations: {e}")
        return []


def read_conversation_by_id(conversation_id: str) -> dict | None:
    """Busca uma conversa pelo ID."""
    try:
        res = _client.table("conversations") \
            .select("*") \
            .eq("id", conversation_id) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"ERRO  read_conversation_by_id: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEITURA — Communities + Tags de afiliado
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Mapeamento: nome da comunidade → etiquetas por marketplace
# Expandir conforme novas comunidades forem onboardadas
_tags_path = "./comunidades.json"
with open(_tags_path, "r", encoding="utf-8") as f:
    COMMUNITY_TAGS = json.load(f)


def read_community_by_id(community_id: str) -> dict | None:
    """Busca uma comunidade pelo ID na tabela communities."""
    try:
        res = _client.table("communities") \
            .select("*") \
            .eq("id", community_id) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"ERRO  read_community_by_id: {e}")
        return None


def get_affiliate_tag(community_id: str, marketplace: str) -> str | None:
    """
    Retorna a etiqueta de afiliado da comunidade pra um marketplace.

    Fluxo:
      1. Busca o nome da comunidade pelo community_id
      2. Procura no COMMUNITY_TAGS a etiqueta do marketplace

    Returns:
        A etiqueta (ex: "amordebichocampinas") ou None se não encontrar.

    Uso:
        tag = get_affiliate_tag(conv["community_id"], "mercadolivre")
        # → "amordebichocampinas"
    """
    community = read_community_by_id(community_id)
    if not community:
        print(f"AVISO  Comunidade {community_id} não encontrada.")
        return None

    community_name = community.get("name", "")
    tags = COMMUNITY_TAGS.get(community_name)

    if not tags:
        print(f"AVISO  Sem tags configuradas para '{community_name}'.")
        return None

    tag = tags.get(marketplace)
    if not tag:
        print(f"AVISO  '{community_name}' não tem tag para '{marketplace}'.")

    return tag


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEITURA — Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def read_messages_with_links(conversation_id: str, limit: int = 50) -> list[dict]:
    """
    Mensagens de cliente que contêm link, numa conversa específica.
    Filtra via ILIKE '%http%' direto no Postgres.
    """
    try:
        res = _client.table("messages") \
            .select("*") \
            .eq("conversation_id", conversation_id) \
            .eq("sender_type", "client") \
            .ilike("text", "%http%") \
            .order("created_at", desc=False) \
            .limit(limit) \
            .execute()
        return res.data or []
    except Exception as e:
        print(f"ERRO  read_messages_with_links: {e}")
        return []


def read_all_link_messages(limit: int = 50) -> list[dict]:
    """
    Todas as mensagens de clientes com link, de qualquer conversa.
    Útil pra varredura geral no startup.
    """
    try:
        res = _client.table("messages") \
            .select("*") \
            .eq("sender_type", "client") \
            .ilike("text", "%http%") \
            .order("created_at", desc=False) \
            .limit(limit) \
            .execute()
        return res.data or []
    except Exception as e:
        print(f"ERRO  read_all_link_messages: {e}")
        return []


def read_message_by_id(message_id: str) -> dict | None:
    """Busca uma mensagem pelo ID."""
    try:
        res = _client.table("messages") \
            .select("*") \
            .eq("id", message_id) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"ERRO  read_message_by_id: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INSERÇÃO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def insert_message(
    id: str,
    text: str,
    conversation_id: str | None = None,
    sender_type: str | None = None,
    message_type: str | None = None,
    client_token: str | None = None,
    auto_kind: str | None = None,
    image_url: str | None = None,
) -> dict | None:
    """
    Insere uma mensagem na tabela `messages`.

    Campos obrigatórios: id, text.
    Os demais são opcionais conforme o schema real.
    """
    row = {"id": id, "text": text}

    if conversation_id is not None:
        row["conversation_id"] = conversation_id
    if sender_type is not None:
        row["sender_type"] = sender_type
    if message_type is not None:
        row["message_type"] = message_type
    if client_token is not None:
        row["client_token"] = client_token
    if auto_kind is not None:
        row["auto_kind"] = auto_kind
    if image_url is not None:
        row["image_url"] = image_url

    try:
        res = _client.table("messages").insert(row).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"ERRO  insert_message: {e}")
        return None


def insert_bot_response(
    id: str,
    text: str,
    conversation_id: str,
    client_token: str | None = None,
) -> dict | None:
    """Atalho pra inserir resposta do bot."""
    return insert_message(
        id=id,
        text=text,
        conversation_id=conversation_id,
        sender_type="bot",
        message_type="text",
        client_token=client_token,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ATUALIZAÇÃO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_message(message_id: str, **fields) -> dict | None:
    """
    Atualiza campos de uma mensagem.

    Uso:
        update_message("id-aqui", text="novo texto", auto_kind="affiliate")
    """
    if not fields:
        return None

    try:
        res = _client.table("messages") \
            .update(fields) \
            .eq("id", message_id) \
            .execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"ERRO  update_message: {e}")
        return None


def update_conversation(conversation_id: str, **fields) -> dict | None:
    """
    Atualiza campos de uma conversa.

    Uso:
        update_conversation("id-aqui", status="closed", claimed_by="agent-123")
    """
    if not fields:
        return None

    try:
        res = _client.table("conversations") \
            .update(fields) \
            .eq("id", conversation_id) \
            .execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"ERRO  update_conversation: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DELEÇÃO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def delete_message(message_id: str) -> bool:
    """Remove uma mensagem pelo ID."""
    try:
        res = _client.table("messages") \
            .delete() \
            .eq("id", message_id) \
            .execute()
        return bool(res.data)
    except Exception as e:
        print(f"ERRO  delete_message: {e}")
        return False