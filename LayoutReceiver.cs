using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

// === CLASSES DE SÉRIALISATION ===
[System.Serializable]
public class ApiLayoutResponse
{
    public string status;
    public List<RoomDto> rooms;
    public HouseDto house;
}

[System.Serializable]
public class HouseDto
{
    public string house_id;
    public float surface_totale;
    public float surface_utilisee;
}

[System.Serializable]
public class RoomDoor
{
    public string id;
    public string connected_to;
    public float width;
    public string type;
    public Vec3 position;
}

[System.Serializable]
public class RoomDto
{
    public string id;
    public string type;
    public string label;
    public Vec3 position;
    public Dims dimensions;
    public List<RoomDoor> doors;
}

[System.Serializable]
public class Vec3
{
    public float x;
    public float y;
    public float z;
}

[System.Serializable]
public class Dims
{
    public float width;
    public float depth;
    public float height;
}

public class LayoutReceiver : MonoBehaviour
{
    [Header("Configuration API")]
    public string apiBaseUrl = "http://127.0.0.1:8000";
    public string houseId = "maison_001";

    [Header("Auto-Refresh Temps Réel")]
    public bool enableAutoRefresh = true;  // ✅ ACTIVÉ PAR DÉFAUT
    public float refreshInterval = 2f;     // Refresh toutes les 2 secondes

    [Header("Options")]
    public GameObject roomPrefab;

    private Dictionary<string, GameObject> spawnedRooms = new Dictionary<string, GameObject>();
    private float lastPollTime = 0f;
    private int lastRoomCount = 0;
    private float lastSurface = 0f;

    void Start()
    {
        if (enableAutoRefresh)
        {
            Debug.Log("🔄 Auto-refresh activé (toutes les " + refreshInterval + "s)");
            Debug.Log("👁️ Unity surveille les changements en temps réel...");
        }
    }

    void Update()
    {
        // Auto-refresh toutes les X secondes
        if (enableAutoRefresh)
        {
            lastPollTime += Time.deltaTime;
            if (lastPollTime >= refreshInterval)
            {
                FetchLayoutSilent();
                lastPollTime = 0f;
            }
        }
    }

    // Version silencieuse pour l'auto-refresh
    private void FetchLayoutSilent()
    {
        StartCoroutine(GetLayoutCoroutine(false));
    }

    // Refresh manuel (si besoin)
    [ContextMenu("Rafraîchir maintenant")]
    public void FetchLayout()
    {
        StartCoroutine(GetLayoutCoroutine(true));
    }

    IEnumerator GetLayoutCoroutine(bool showLogs = true)
    {
        string url = $"{apiBaseUrl}/api/layout/{houseId}";

        using (UnityWebRequest req = UnityWebRequest.Get(url))
        {
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    ApiLayoutResponse response = JsonUtility.FromJson<ApiLayoutResponse>(req.downloadHandler.text);

                    if (response.rooms != null && response.rooms.Count > 0)
                    {
                        // Détecte les changements
                        bool hasChanged = (response.rooms.Count != lastRoomCount) ||
                                         (response.house != null && response.house.surface_utilisee != lastSurface);

                        if (hasChanged)
                        {
                            RenderRooms(response.rooms);
                            lastRoomCount = response.rooms.Count;
                            lastSurface = response.house != null ? response.house.surface_utilisee : 0f;

                            if (showLogs)
                            {
                                Debug.Log($"✅ {response.rooms.Count} pièce(s) mise(s) à jour");
                                if (response.house != null)
                                {
                                    Debug.Log($"📊 Surface: {response.house.surface_utilisee}/{response.house.surface_totale} m²");
                                }
                            }
                        }
                    }
                }
                catch (System.Exception e)
                {
                    if (showLogs) Debug.LogError($"❌ Erreur JSON: {e.Message}");
                }
            }
            else if (req.responseCode == 404)
            {
                // Silencieux en 404 (maison pas encore créée)
            }
        }
    }

    void RenderRooms(List<RoomDto> rooms)
    {
        // Nettoyage
        foreach (var go in spawnedRooms.Values)
        {
            if (go != null) Destroy(go);
        }
        spawnedRooms.Clear();

        // Génération
        foreach (var room in rooms)
        {
            CreateRoomFull(room);
        }

        Debug.Log($"🏠 Scène mise à jour : {rooms.Count} pièce(s)");
    }

    void CreateRoomFull(RoomDto room)
    {
        GameObject roomObj = new GameObject($"{room.type}_{room.id}");
        // La position locale est le coin inférieur gauche dans notre logique, 
        // Unity a son pivot au centre des primitifs.
        float cx = room.position.x + (room.dimensions.width / 2.0f);
        float cz = room.position.z + (room.dimensions.depth / 2.0f);
        roomObj.transform.position = new Vector3(cx, 0, cz);

        // Floor
        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.name = "Floor";
        floor.transform.parent = roomObj.transform;
        floor.transform.localPosition = new Vector3(0, 0, 0);
        // Plane is 10x10 units in Unity by default
        floor.transform.localScale = new Vector3(room.dimensions.width / 10.0f, 1, room.dimensions.depth / 10.0f);
        
        Renderer floorRend = floor.GetComponent<Renderer>();
        if (floorRend != null) floorRend.material.color = GetColorByType(room.type);

        // Walls
        float wallThickness = 0.2f;
        float h = room.dimensions.height;
        float w = room.dimensions.width;
        float d = room.dimensions.depth;

        // Identifions si nous avons des portes sur les murs
        bool northDoor = false, southDoor = false, eastDoor = false, westDoor = false;

        if (room.doors != null)
        {
            foreach (var door in room.doors)
            {
                // Vérifier grossièrement si la porte est sur l'un des murs par rapport aux coordonnées globales de la porte
                // et la bb de la pièce
                float dx = door.position.x;
                float dz = door.position.z;

                float rLeft = room.position.x;
                float rRight = room.position.x + room.dimensions.width;
                float rBottom = room.position.z;
                float rTop = room.position.z + room.dimensions.depth;
                
                float epsilon = 0.1f;

                if (Mathf.Abs(dz - rTop) <= epsilon) northDoor = true;
                if (Mathf.Abs(dz - rBottom) <= epsilon) southDoor = true;
                if (Mathf.Abs(dx - rRight) <= epsilon) eastDoor = true;
                if (Mathf.Abs(dx - rLeft) <= epsilon) westDoor = true;
            }
        }

        // North
        if (northDoor) CreateWallWithDoor(roomObj, "Wall_N", new Vector3(0, h/2, d/2), new Vector3(w, h, wallThickness), true);
        else CreateWall(roomObj, "Wall_N", new Vector3(0, h/2, d/2), new Vector3(w, h, wallThickness));
        
        // South
        if (southDoor) CreateWallWithDoor(roomObj, "Wall_S", new Vector3(0, h/2, -d/2), new Vector3(w, h, wallThickness), true);
        else CreateWall(roomObj, "Wall_S", new Vector3(0, h/2, -d/2), new Vector3(w, h, wallThickness));
        
        // East
        if (eastDoor) CreateWallWithDoor(roomObj, "Wall_E", new Vector3(w/2, h/2, 0), new Vector3(wallThickness, h, d), false);
        else CreateWall(roomObj, "Wall_E", new Vector3(w/2, h/2, 0), new Vector3(wallThickness, h, d));
        
        // West
        if (westDoor) CreateWallWithDoor(roomObj, "Wall_W", new Vector3(-w/2, h/2, 0), new Vector3(wallThickness, h, d), false);
        else CreateWall(roomObj, "Wall_W", new Vector3(-w/2, h/2, 0), new Vector3(wallThickness, h, d));

        spawnedRooms[room.id] = roomObj;
    }
    
    void CreateWall(GameObject parent, string name, Vector3 pos, Vector3 scale)
    {
        GameObject wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
        wall.name = name;
        wall.transform.parent = parent.transform;
        wall.transform.localPosition = pos;
        wall.transform.localScale = scale;
        wall.GetComponent<Renderer>().material.color = Color.white;
    }

    void CreateWallWithDoor(GameObject parent, string name, Vector3 pos, Vector3 scale, bool isHorizontal)
    {
        // Pour simplifier drastiquement, on divise le mur en deux petits segments créant un trou au milieu de 1m de large
        float doorWidth = 1.0f;
        
        if (isHorizontal)
        {
            // Ouest du trou
            float w1 = (scale.x - doorWidth) / 2.0f;
            CreateWall(parent, name + "_L", pos + new Vector3(-(w1/2 + doorWidth/2), 0, 0), new Vector3(w1, scale.y, scale.z));
            // Est du trou
            float w2 = (scale.x - doorWidth) / 2.0f;
            CreateWall(parent, name + "_R", pos + new Vector3(w2/2 + doorWidth/2, 0, 0), new Vector3(w2, scale.y, scale.z));
        }
        else
        {
            // Sud du trou
            float d1 = (scale.z - doorWidth) / 2.0f;
            CreateWall(parent, name + "_L", pos + new Vector3(0, 0, -(d1/2 + doorWidth/2)), new Vector3(scale.x, scale.y, d1));
            // Nord du trou
            float d2 = (scale.z - doorWidth) / 2.0f;
            CreateWall(parent, name + "_R", pos + new Vector3(0, 0, (d2/2 + doorWidth/2)), new Vector3(scale.x, scale.y, d2));
        }
    }

    Color GetColorByType(string type)
    {
        if (string.IsNullOrEmpty(type)) return Color.white;
        string t = type.ToLowerInvariant();
        
        if (t.Contains("salon")) return new Color(0.9f, 0.8f, 0.7f);
        if (t.Contains("chambre")) return new Color(0.7f, 0.8f, 0.9f);
        if (t.Contains("cuisine")) return new Color(0.8f, 0.9f, 0.7f);
        if (t.Contains("bain")) return new Color(0.9f, 0.7f, 0.8f);
        if (t.Contains("couloir")) return new Color(0.6f, 0.6f, 0.6f);
        
        return Color.white;
    }
}