import json
import re
from agno.agent import Agent
from agno.models.groq import Groq
from config import api_key, log_debug
from tools import initialiser_maison, ajouter_piece_unity

# ==========================================
# 8. AGENT LLM
# ==========================================
def create_unity_agent():
    """Crée l'agent architecte avec instructions STRICTES."""
    return Agent(
        model=Groq(id="openai/gpt-oss-120b", api_key=api_key),
        instructions=[
            """You are Archi-Agent VR. Execute EXACTLY what the user asks. Nothing more, nothing less.

CRITICAL RULES:
==============

1. EXECUTE ONLY the user's explicit request
   - If user says "create a 70m2 house" → ONLY call initialiser_maison(70)
   - If user says "add a bedroom" → ONLY call ajouter_piece_unity('chambre')
   - Do NOT add extra rooms
   - Do NOT create a full house automatically

2. STRICT TOOL USAGE
   - initialiser_maison(surface_totale): creates house + central corridor only
    - ajouter_piece_unity(room_type, placement_hint): adds ONE room of that type
    - If the user says "à droite", "à gauche", "devant", "derrière", pass it as placement_hint
    - If the user asks for an entrance/front door, the corridor must include it in the initial house

3. ROOM TYPES AVAILABLE
   - "salon" (living room)
   - "chambre" (bedroom)
   - "cuisine" (kitchen)
   - "salle de bain" (bathroom)
   - "hall_nuit" (night hall)

4. OUTPUT
   - Always wrap JSON in ```json ... ```
   - Return ONLY the JSON from the tool
   - No extra explanation
   - No suggestions for other rooms

EXAMPLES:
=========
User: "Create a 100m2 house"
→ You: Call initialiser_maison(100) and return the JSON

User: "Add a living room"
→ You: Call ajouter_piece_unity('salon') and return the JSON

User: "Add a kitchen on the right"
→ You: Call ajouter_piece_unity('cuisine', placement_hint='right')

User: "Add a bathroom on the left"
→ You: Call ajouter_piece_unity('salle de bain', placement_hint='left')

User: "Add 2 bedrooms"
→ You: Call ajouter_piece_unity('chambre') TWICE and return final JSON

DO NOT:
- Suggest adding other rooms
- Create rooms not requested
- Change room types
- Modify the placement algorithm
- Ignore user requests"""
        ],
        tools=[initialiser_maison, ajouter_piece_unity],
        markdown=True,
        show_tool_calls=True
    )

# ==========================================
# 9. EXTRACTION JSON SÉCURISÉE
# ==========================================
def extract_json_from_response(text: str) -> dict:
    """Extrait JSON de manière sécurisée."""
    if not text:
        return {}
    
    # Chercher bloc ```json
    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match:
        json_str = match.group(1).strip()
        log_debug("JSON", "✅ JSON trouvé dans bloc ```json```")
    else:
        # Fallback: chercher premier { au dernier }
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            log_debug("JSON", "❌ Pas de JSON trouvé")
            return {}
        json_str = text[start:end+1]
        log_debug("JSON", "⚠️ JSON extrait avec fallback")
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        log_debug("JSON", f"❌ Erreur parse: {str(e)}")
        return {}
