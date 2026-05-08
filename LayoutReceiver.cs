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
public class RoomDto
{
    public string id;
    public string type;
    public string label;
    public Vec3 position;
    public Dims dimensions;
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
            Vector3 pos = new Vector3(room.position.x, 0f, room.position.z);
            Vector3 scale = new Vector3(room.dimensions.width, room.dimensions.height, room.dimensions.depth);

            GameObject obj;
            if (roomPrefab != null)
            {
                obj = Instantiate(roomPrefab, pos, Quaternion.identity);
                obj.name = $"{room.type}_{room.id}";
            }
            else
            {
                obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
                obj.name = $"{room.type}_{room.id}";
                obj.transform.position = new Vector3(pos.x, scale.y / 2f, pos.z);
                obj.transform.localScale = scale;

                var renderer = obj.GetComponent<Renderer>();
                if (renderer != null) renderer.material.color = GetColorByType(room.type);
            }

            spawnedRooms[room.id] = obj;
        }

        Debug.Log($"🏠 Scène mise à jour : {rooms.Count} pièce(s)");
    }

    Color GetColorByType(string type)
    {
        string t = type?.ToLowerInvariant();
        return t switch
        {
            "salon" => new Color(0.9f, 0.8f, 0.7f),
            "chambre" => new Color(0.7f, 0.8f, 0.9f),
            "cuisine" => new Color(0.8f, 0.9f, 0.7f),
            "salle de bain" => new Color(0.9f, 0.7f, 0.8f),
            "couloir" => new Color(0.6f, 0.6f, 0.6f),
            _ => Color.white
        };
    }
}