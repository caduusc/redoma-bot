from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL       = os.environ["SUPABASE_URL"]
SUPABASE_KEY       = os.environ["SUPABASE_KEY"]
BOT_SECRET         = os.environ.get("BOT_SECRET", "")
ML_EMAIL           = os.environ.get("ML_EMAIL", "")
ML_PASSWORD        = os.environ.get("ML_PASSWORD", "")