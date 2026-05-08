from typing import List, Dict, Tuple, Set
from config import (GRID_SIZE, MIN_ROOM_GAP, ROOM_RATIOS, MIN_ROOM_SIZES, MAX_ROOM_SIZES, 
                    DEFAULT_HEIGHT, DOOR_WIDTH, WINDOW_WIDTH, WALL_THICKNESS, log_debug)

# ==========================================
# 3. GRILLE & GÉOMÉTRIE & PLACEMENT
# ==========================================
class GridMap:
    """Gestion intelligente de la grille pour éviter les chevauchements."""
    
    def __init__(self, world_width: float, world_depth: float):
        self.world_width = world_width
        self.world_depth = world_depth
        self.grid_width = int(world_width / GRID_SIZE) + 1
        self.grid_depth = int(world_depth / GRID_SIZE) + 1
        self.occupied_cells: Set[Tuple[int, int]] = set()
        log_debug("GRID", f"Grille créée: {self.grid_width}x{self.grid_depth} ({GRID_SIZE}m cells)")
    
    def world_to_grid(self, x: float, z: float) -> Tuple[int, int]:
        """Convertit coordonnées monde en coordonnées grille."""
        gx = int(x / GRID_SIZE)
        gz = int(z / GRID_SIZE)
        return (gx, gz)
    
    def grid_to_world(self, gx: int, gz: int) -> Tuple[float, float]:
        """Convertit coordonnées grille en coordonnées monde."""
        x = gx * GRID_SIZE
        z = gz * GRID_SIZE
        return (x, z)
    
    def reserve_cells(self, x: float, z: float, width: float, depth: float) -> bool:
        """Réserve les cellules pour une pièce."""
        gx1, gz1 = self.world_to_grid(x, z)
        gx2, gz2 = self.world_to_grid(x + width, z + depth)
        
        cells_to_reserve = []
        for gx in range(gx1, gx2 + 1):
            for gz in range(gz1, gz2 + 1):
                if (gx, gz) in self.occupied_cells:
                    log_debug("COLLISION", f"Cellule ({gx},{gz}) déjà occupée")
                    return False
                cells_to_reserve.append((gx, gz))
        
        for cell in cells_to_reserve:
            self.occupied_cells.add(cell)
        
        log_debug("GRID", f"✅ {len(cells_to_reserve)} cellules réservées")
        return True
    
    def is_area_free(self, x: float, z: float, width: float, depth: float) -> bool:
        """Vérifie si une zone est libre."""
        gx1, gz1 = self.world_to_grid(x, z)
        gx2, gz2 = self.world_to_grid(x + width, z + depth)
        
        for gx in range(gx1, gx2 + 1):
            for gz in range(gz1, gz2 + 1):
                if (gx, gz) in self.occupied_cells:
                    return False
        return True

class RoomPlacement:
    """Placement intelligent des pièces avec grille."""
    
    @staticmethod
    def get_dynamic_dimensions(room_type: str, total_surface: float) -> Dict:
        """Calcule les dimensions dynamiques avec contraintes min/max."""
        ratio = ROOM_RATIOS.get(room_type, 0.10)
        target_surface = total_surface * ratio
        
        # Appliquer les contraintes
        min_size = MIN_ROOM_SIZES.get(room_type, 2.0)
        max_size = MAX_ROOM_SIZES.get(room_type, 100.0)
        target_surface = max(min_size, min(max_size, target_surface))
        
        # Calculer dimensions
        width = round(target_surface ** 0.5, 2)
        depth = round(target_surface / width, 2)
        
        # Arrondir à la grille
        width = round(width / GRID_SIZE) * GRID_SIZE
        depth = round(depth / GRID_SIZE) * GRID_SIZE
        
        return {
            "width": float(width),
            "depth": float(depth),
            "height": DEFAULT_HEIGHT,
            "surface": round(width * depth, 2)
        }
    
    @staticmethod
    def find_position(room_type: str, dims: Dict, existing_rooms: List[Dict], grid: GridMap) -> Tuple[float, float]:
        """Place la pièce intelligemment selon le type."""
        hallway = next((r for r in existing_rooms if r["type"] == "couloir"), None)
        if not hallway:
            log_debug("PLACEMENT", "❌ Pas de couloir trouvé")
            return 0.0, 0.0
        
        hx, hz = hallway["position"]["x"], hallway["position"]["z"]
        hw, hd = hallway["dimensions"]["width"], hallway["dimensions"]["depth"]
        w, d = dims["width"], dims["depth"]
        
        log_debug("PLACEMENT", f"Placement de {room_type} ({w}x{d}m) près couloir ({hx},{hz})")
        
        # CAS 1 : Chambre, salle de bain, cuisine → placer à gauche/droite du couloir
        if room_type in ["chambre", "salle de bain", "cuisine"]:
            for side in ["gauche", "droite"]:
                tx = (hx - w - MIN_ROOM_GAP) if side == "gauche" else (hx + hw + MIN_ROOM_GAP)
                tz = hz
                
                # Balayer verticalement le long du couloir
                max_tz = hz + hd + 5.0
                attempts = 0
                while tz <= max_tz and attempts < 20:
                    if grid.is_area_free(tx, tz, w, d):
                        if grid.reserve_cells(tx, tz, w, d):
                            log_debug("PLACEMENT", f"✅ {room_type} placé à {side}: ({tx:.2f}, {tz:.2f})")
                            return tx, tz
                    tz += GRID_SIZE
                    attempts += 1
        
        # CAS 2 : Salon → derrière le couloir, centré
        elif room_type == "salon":
            tx = hx + (hw / 2) - (w / 2)
            tz = hz + hd + MIN_ROOM_GAP
            if grid.is_area_free(tx, tz, w, d):
                if grid.reserve_cells(tx, tz, w, d):
                    log_debug("PLACEMENT", f"✅ Salon placé: ({tx:.2f}, {tz:.2f})")
                    return tx, tz
        
        # CAS 3 : Hall_nuit → entre couloir et chambres
        elif room_type == "hall_nuit":
            tx = hx + (hw / 2) - (w / 2)
            tz = hz + hd + MIN_ROOM_GAP
            if grid.is_area_free(tx, tz, w, d):
                if grid.reserve_cells(tx, tz, w, d):
                    log_debug("PLACEMENT", f"✅ Hall nuit placé: ({tx:.2f}, {tz:.2f})")
                    return tx, tz
        
        # FALLBACK : Chercher une zone libre n'importe où
        log_debug("PLACEMENT", f"⚠️ Fallback recherche pour {room_type}")
        search_x = hx - 20.0
        search_z = hz - 10.0
        while search_z < hz + 30.0:
            if grid.is_area_free(search_x, search_z, w, d):
                if grid.reserve_cells(search_x, search_z, w, d):
                    log_debug("PLACEMENT", f"✅ {room_type} placé en fallback: ({search_x:.2f}, {search_z:.2f})")
                    return search_x, search_z
            search_z += GRID_SIZE
        
        # Dernier recours (ne devrait presque jamais arriver ici)
        log_debug("PLACEMENT", f"❌ IMPOSSIBLE de placer {room_type}, fallback extrême")
        return hx + hw + 10.0, hz
    
    @staticmethod
    def find_adjacent_rooms(new_x: float, new_z: float, new_w: float, new_d: float, 
                           existing_rooms: List[Dict], tolerance: float = 0.2) -> List[str]:
        """Trouve les pièces adjacentes avec marge architecturale."""
        adjacent = []
        for r in existing_rooms:
            rx, rz = r["position"]["x"], r["position"]["z"]
            rw, rd = r["dimensions"]["width"], r["dimensions"]["depth"]
            
            # Adjacence horizontale
            if (abs(new_x - (rx + rw)) < tolerance or abs((new_x + new_w) - rx) < tolerance):
                if not (new_z + new_d < rz or new_z > rz + rd):
                    adjacent.append(r["id"])
            
            # Adjacence verticale
            elif (abs(new_z - (rz + rd)) < tolerance or abs((new_z + new_d) - rz) < tolerance):
                if not (new_x + new_w < rx or new_x > rx + rw):
                    adjacent.append(r["id"])
        
        return adjacent

def generate_doors(rooms: List[Dict]) -> Dict[str, List[Dict]]:
    """Génère les portes entre pièces adjacentes."""
    doors = {}
    for room in rooms:
        doors[room["id"]] = []
        for adjacent_id in room["metadata"]["adjacent_to"]:
            doors[room["id"]].append({
                "id": f"door_{room['id']}_to_{adjacent_id}",
                "connected_to": adjacent_id,
                "width": DOOR_WIDTH,
                "type": "internal_door"
            })
    return doors

def generate_windows(rooms: List[Dict]) -> Dict[str, List[Dict]]:
    """Génère les fenêtres (surtout pour chambres)."""
    windows = {}
    for room in rooms:
        windows[room["id"]] = []
        if room["type"] == "chambre":
            # Au moins 1 fenêtre pour les chambres
            windows[room["id"]].append({
                "id": f"window_{room['id']}_1",
                "width": WINDOW_WIDTH,
                "position": "north_wall",
                "type": "double_window"
            })
    return windows

def generate_walls(room: Dict, existing_rooms: List[Dict]) -> List[Dict]:
    """Génère les murs d'une pièce."""
    walls = []
    rx, rz = room["position"]["x"], room["position"]["z"]
    rw, rd = room["dimensions"]["width"], room["dimensions"]["depth"]
    
    # 4 murs
    walls.append({
        "id": f"wall_{room['id']}_north",
        "orientation": "north",
        "length": rw,
        "thickness": WALL_THICKNESS,
        "position": {"x": rx, "z": rz + rd}
    })
    walls.append({
        "id": f"wall_{room['id']}_south",
        "orientation": "south",
        "length": rw,
        "thickness": WALL_THICKNESS,
        "position": {"x": rx, "z": rz}
    })
    walls.append({
        "id": f"wall_{room['id']}_east",
        "orientation": "east",
        "length": rd,
        "thickness": WALL_THICKNESS,
        "position": {"x": rx + rw, "z": rz}
    })
    walls.append({
        "id": f"wall_{room['id']}_west",
        "orientation": "west",
        "length": rd,
        "thickness": WALL_THICKNESS,
        "position": {"x": rx, "z": rz}
    })
    
    return walls
