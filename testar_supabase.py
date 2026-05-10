import sys, os, uuid
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

from config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("OK  Conexao estabelecida com Supabase")
print(f"    URL: {SUPABASE_URL[:40]}...")

# --- Teste de leitura --------------------------------------------------------
try:
    res = client.table("messages").select("id").limit(1).execute()
    print(f"OK  Leitura OK  ->  {len(res.data)} registro(s) retornado(s)")
except Exception as e:
    print(f"ERRO  Leitura falhou: {e}")

# --- Teste de insercao + remocao ---------------------------------------------
try:
    inserido = client.table("messages").insert({
        "id":              str(uuid.uuid4()),
        "conversation_id": "00000000-0000-0000-0000-000000000000",
        "sender_type":     "bot",
        "message_type":    "text",
        "text":            "Teste de permissao",
    }).execute()

    novo_id = inserido.data[0]["id"]
    print(f"OK  Insercao OK  ->  id gerado: {novo_id}")

    client.table("messages").delete().eq("id", novo_id).execute()
    print(f"OK  Remocao OK   ->  registro de teste apagado")

except Exception as e:
    print(f"ERRO  Insercao falhou: {e}")
