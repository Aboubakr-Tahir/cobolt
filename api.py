import json
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

# Ajoute le dossier parent au PATH pour les imports relatifs
sys.path.insert(0, str(Path(__file__).parent))

# Import depuis le même dossier (src)
from llm_agent import create_unity_agent, extract_json_from_response
from database import clean_doc

app = FastAPI(title="Archi-Agent VR API")

# Autorise Unity à appeler l'API (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connexion DB
mongo_client = MongoClient("mongodb://admin:admin123@localhost:27017/admin?authSource=admin")
db = mongo_client["house_design"]
rooms_col = db["rooms"]
houses_col = db["houses"]

# Initialisation unique de l'agent
agent = create_unity_agent()

class ChatRequest(BaseModel):
    message: str
    house_id: str = "maison_001"

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        res = agent.run(req.message)
        layout = extract_json_from_response(res.content)
        return {"status": "ok", "reply": res.content, "layout": layout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/layout/{house_id}")
async def get_layout(house_id: str):
    try:
        # ✅ CORRECTION: Récupère TOUTES les pièces (pas de filtre house_id)
        # Car les pièces ne sont pas stockées avec house_id dans agent.py
        rooms = [clean_doc(r) for r in rooms_col.find({}, projection={"_id": 0})]
        
        # Cherche la maison
        house = houses_col.find_one({"house_id": house_id}, projection={"_id": 0})
        
        if not rooms:
            raise HTTPException(status_code=404, detail="Aucune pièce trouvée. Initialisez d'abord une maison via agent.py")
        
        return {"status": "ok", "house": house, "rooms": rooms}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)