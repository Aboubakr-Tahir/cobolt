import json
from datetime import datetime
from typing import Optional
from config import log_debug, DEFAULT_HEIGHT, WALL_THICKNESS, DOOR_WIDTH, WINDOW_WIDTH, get_room_zone
from database import rooms_collection, house_collection, clean_doc, clear_database
from spatial import GridMap, RoomPlacement, generate_walls
from validator import HouseValidator, score_layout

# ==========================================
# 7. OUTILS DE L'AGENT (TOOLS)
# ==========================================
def initialiser_maison(surface_totale: float) -> str:
    """Initialise une nouvelle maison avec couloir central."""
    try:
        surface_totale = float(surface_totale)
    except (ValueError, TypeError):
        return json.dumps({"status": "error", "message": "surface_totale doit être un nombre"})
    
    if rooms_collection is None or house_collection is None:
        return json.dumps({"status": "error", "message": "MongoDB non connecté"})
    
    clear_database()
    
    log_debug("INIT", f"Création maison {surface_totale}m²")
    
    hw = 2.0
    hd = round(surface_totale * 0.12 / hw, 2)
    house_id = "maison_001"
    
    couloir = {
        "id": "couloir_1",
        "type": "couloir",
        "label": "Couloir Central",
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "dimensions": {"width": float(hw), "depth": float(hd), "height": DEFAULT_HEIGHT},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "visual": {
            "floor_color": "#A0A0A0",
            "wall_color": "#FFFFFF",
            "opacity": 1.0,
            "wall_thickness": WALL_THICKNESS
        },
        "metadata": {
            "surface": round(hw * hd, 2),
            "adjacent_to": [],
            "has_door": False,
            "privacy_level": 0,
            "natural_light": 0,
            "circulation_score": 100,
            "architectural_score": 0,
            "zone": "circulation"
        },
        "doors": [],
        "windows": [],
        "walls": generate_walls({"id": "couloir_1", "position": {"x": 0.0, "z": 0.0},
                                "dimensions": {"width": hw, "depth": hd}}, [])
    }
    
    house_collection.insert_one({
        "house_id": house_id,
        "surface_totale": surface_totale,
        "surface_utilisee": round(hw * hd, 2),
        "created_at": datetime.now().isoformat(),
        "layout_valid": True,
        "validation_errors": [],
        "orientation": "north",
        "style": "modern"
    })
    rooms_collection.insert_one(couloir)
    
    log_debug("INIT", "✅ Maison initialisée")
    
    return json.dumps({
        "status": "success",
        "action": "init_house",
        "house_id": house_id,
        "timestamp": datetime.now().isoformat(),
        "rooms": [clean_doc(couloir)],
        "metadata": {
            "surface_totale": surface_totale,
            "surface_utilisee": round(hw * hd, 2),
            "unite": "meters",
            "layout_valid": True,
            "validation_errors": []
        }
    }, ensure_ascii=False)

def ajouter_piece_unity(room_type: str, label: Optional[str] = None) -> str:
    """Ajoute une pièce avec validation complète."""
    if rooms_collection is None or house_collection is None:
        return json.dumps({"status": "error", "message": "MongoDB non connecté"})
    
    house = clean_doc(house_collection.find_one({}, sort=[("created_at", -1)], projection={"_id": 0}))
    if not house:
        return json.dumps({"status": "error", "message": "Initialise d'abord la maison"})
    
    existing = [clean_doc(r) for r in rooms_collection.find({}, projection={"_id": 0})]
    
    log_debug("ROOM_ADD", f"Ajout de {room_type}")
    
    # Créer grille
    grid = GridMap(100.0, 100.0)  # Monde assez grand
    for room in existing:
        x, z = room["position"]["x"], room["position"]["z"]
        w, d = room["dimensions"]["width"], room["dimensions"]["depth"]
        grid.reserve_cells(x, z, w, d)
    
    # Calculer dimensions
    dims = RoomPlacement.get_dynamic_dimensions(room_type, house["surface_totale"])
    tx, tz = RoomPlacement.find_position(room_type, dims, existing, grid)
    
    count = len([r for r in existing if r["type"] == room_type]) + 1
    room_id = f"{room_type}_{count}"
    
    colors = {
        "salon": "#E8D5C4",
        "chambre": "#C4D7E8",
        "cuisine": "#D5E8C4",
        "salle de bain": "#E8C4D7",
        "hall_nuit": "#F0F0F0"
    }
    
    adjacent_rooms = RoomPlacement.find_adjacent_rooms(tx, tz, dims["width"], dims["depth"], existing)
    if not adjacent_rooms:
        adjacent_rooms = ["couloir_1"]
    
    # Créer la pièce
    new_room = {
        "id": room_id,
        "type": room_type,
        "label": label or f"{room_type.capitalize()} {count}",
        "position": {"x": float(tx), "y": 0.0, "z": float(tz)},
        "dimensions": {
            "width": float(dims["width"]),
            "depth": float(dims["depth"]),
            "height": float(dims["height"])
        },
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "visual": {
            "floor_color": colors.get(room_type, "#FFFFFF"),
            "wall_color": "#FFFFFF",
            "opacity": 1.0,
            "wall_thickness": WALL_THICKNESS
        },
        "zone": get_room_zone(room_type),
        "metadata": {
            "surface": float(dims["surface"]),
            "adjacent_to": adjacent_rooms,
            "has_door": len(adjacent_rooms) > 0,
            "door_position": "front",
            "privacy_level": 2 if get_room_zone(room_type) == "private" else 0,
            "natural_light": 1 if room_type == "chambre" else 0,
            "circulation_score": 50,
            "architectural_score": 0
        },
        "doors": [],
        "windows": [],
        "walls": []
    }
    
    # Générer portes et fenêtres pour cette pièce
    if adjacent_rooms:
        new_room["doors"] = [
            {
                "id": f"door_{room_id}_to_{adj}",
                "connected_to": adj,
                "width": DOOR_WIDTH,
                "type": "internal_door"
            }
            for adj in adjacent_rooms
        ]
    
    if room_type == "chambre":
        new_room["windows"] = [
            {
                "id": f"window_{room_id}_1",
                "width": WINDOW_WIDTH,
                "position": "north_wall",
                "type": "double_window"
            }
        ]
    
    new_room["walls"] = generate_walls(new_room, existing)
    
    # Valider
    validator = HouseValidator(house["surface_totale"])
    all_rooms_to_validate = existing + [new_room]
    
    if not validator.validate_all(all_rooms_to_validate):
        log_debug("VALIDATION", f"❌ Validation échouée")
        return json.dumps({
            "status": "error",
            "message": "Placement invalide",
            "errors": validator.errors,
            "warnings": validator.warnings
        })
    
    # Insérer en DB
    try:
        rooms_collection.insert_one(new_room)
        house_collection.update_one(
            {"house_id": house["house_id"]},
            {
                "$inc": {"surface_utilisee": dims["surface"]},
                "$set": {
                    "layout_valid": True,
                    "validation_errors": []
                }
            }
        )
        log_debug("ROOM_ADD", f"✅ {room_type} ajouté en DB")
    except Exception as e:
        log_debug("ERROR", f"Erreur DB: {str(e)}")
        return json.dumps({"status": "error", "message": f"Erreur DB: {str(e)}"})
    
    # Récupérer état final
    updated_rooms = [clean_doc(r) for r in rooms_collection.find({}, projection={"_id": 0})]
    updated_surface = house["surface_utilisee"] + dims["surface"]
    layout_score = score_layout(updated_rooms)
    
    # Retourner une réponse LÉGÈRE (sans murs/fenêtres/portes détaillés)
    lightweight_rooms = []
    for room in updated_rooms:
        lightweight_room = {
            "id": room["id"],
            "type": room["type"],
            "label": room["label"],
            "position": room["position"],
            "dimensions": room["dimensions"],
            "visual": room["visual"],
            "zone": room.get("zone", "unknown"),
            "metadata": room["metadata"],
            "num_doors": len(room.get("doors", [])),
            "num_windows": len(room.get("windows", [])),
            "num_walls": len(room.get("walls", []))
        }
        lightweight_rooms.append(lightweight_room)
    
    return json.dumps({
        "status": "success",
        "action": "add_room",
        "house_id": house["house_id"],
        "timestamp": datetime.now().isoformat(),
        "rooms": lightweight_rooms,
        "metadata": {
            "surface_totale": house["surface_totale"],
            "surface_utilisee": round(updated_surface, 2),
            "unite": "meters",
            "layout_valid": True,
            "validation_errors": [],
            "layout_score": round(layout_score, 1),
            "orientation": house.get("orientation", "north"),
            "style": house.get("style", "modern")
        }
    }, ensure_ascii=False)
