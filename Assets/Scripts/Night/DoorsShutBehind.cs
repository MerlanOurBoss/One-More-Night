using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// At night an appliance door you left open does not stay open: once you have walked away and it is out of sight, it shuts by itself, without a sound.
/// You only find out when you come back.
/// </summary>
public class DoorsShutBehind : MonoBehaviour
{
    static readonly Plane[] Frustum = new Plane[6];

    [SerializeField] NightLoop loop;
    [SerializeField] Camera view;
    [Tooltip("The chance that a door you opened will shut itself.")]
    [SerializeField, Range(0f, 1f)] float chance = 0.6f;
    [Tooltip("Seconds after you opened it, at the earliest and the latest. It waits longer while you are near or looking.")]
    [SerializeField] Vector2 after = new Vector2(6f, 20f);
    [Tooltip("Only once you are this far from it.")]
    [SerializeField] float awayDistance = 2.5f;
    [SerializeField] float shutSeconds = 1.5f;

    readonly List<TransformAnomaly> doors = new List<TransformAnomaly>();
    readonly Dictionary<TransformAnomaly, float> shutAt = new Dictionary<TransformAnomaly, float>();
    readonly HashSet<TransformAnomaly> wasOpen = new HashSet<TransformAnomaly>();

    void Awake()
    {
        foreach (TransformAnomaly door in FindObjectsByType<TransformAnomaly>(FindObjectsInactive.Include, FindObjectsSortMode.None))
        {
            if (door.HandDoor)
                doors.Add(door);
        }
    }

    void Update()
    {
        bool night = loop.CurrentPhase == NightLoop.Phase.Night;
        float now = Time.time;
        foreach (TransformAnomaly door in doors)
        {
            bool open = door.OpenedByHand;
            // Opened just now: decide whether this one will be waiting for you.
            if (open && !wasOpen.Contains(door))
            {
                wasOpen.Add(door);
                if (Random.value < chance)
                    shutAt[door] = now + Random.Range(after.x, after.y);
            }
            else if (!open)
            {
                wasOpen.Remove(door);
                shutAt.Remove(door);
                continue;
            }

            if (!night || !shutAt.TryGetValue(door, out float at) || now < at)
                continue;
            if (Vector3.Distance(view.transform.position, door.Center) < awayDistance || Seen(door))
                continue;
            door.ShutQuietly(shutSeconds);
            shutAt.Remove(door);
            wasOpen.Remove(door);
        }
    }

    bool Seen(TransformAnomaly door)
    {
        Bounds bounds = door.Bounds;
        GeometryUtility.CalculateFrustumPlanes(view, Frustum);
        if (!GeometryUtility.TestPlanesAABB(Frustum, bounds))
            return false;
        Vector3 eye = view.transform.position;
        Vector3 to = bounds.center - eye;
        bool blocked = Physics.Raycast(eye, to.normalized, out RaycastHit hit, to.magnitude, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
            && !door.Owns(hit.collider);
        return !blocked;
    }
}
