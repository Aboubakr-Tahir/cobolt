from pymongo import MongoClient
from bson import ObjectId
from typing import Dict, Optional
from config import log_debug

# ==========================================
# 2. CONNEXION DB & UTILITAIRES
# ==========================================
try:
    mongo_client = MongoClient("mongodb://admin:admin123@localhost:27017/admin?authSource=admin")
    db = mongo_client["house_design"]
    rooms_collection = db["rooms"]
    house_collection = db["houses"]
    log_debug("DATABASE", "✅ MongoDB connecté")
except Exception as e:
    print(f"❌ Erreur MongoDB: {e}")
    rooms_collection = None
    house_collection = None

def clear_database():
    """Vide les collections rooms et houses."""
    if rooms_collection is not None and house_collection is not None:
        rooms_collection.delete_many({})
        house_collection.delete_many({})

def clean_doc(doc: Optional[Dict]) -> Dict:
    """Nettoie un document MongoDB."""
    if doc is None:
        return {}
    cleaned = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, ObjectId):
            cleaned[k] = str(v)
        elif isinstance(v, dict):
            cleaned[k] = clean_doc(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_doc(i) if isinstance(i, dict) else i for i in v]
        else:
            cleaned[k] = v
    return cleaned
