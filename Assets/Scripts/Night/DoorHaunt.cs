using UnityEngine;

/// <summary>
/// The inside doors at night: shut while you slept, and then, one by one, they creak open by themselves.
/// Only when you are close enough to hear it; a door you opened yourself is left alone.
/// </summary>
public class DoorHaunt : MonoBehaviour
{
    [SerializeField] NightLoop loop;
    [SerializeField] Transform player;
    [SerializeField] DoorSwing[] doors = new DoorSwing[0];
    [SerializeField] int fromNight = 2;
    [Tooltip("The chance that a shut door opens itself during the night.")]
    [SerializeField, Range(0f, 1f)] float openChance = 0.7f;
    [Tooltip("Seconds into the night, at the earliest and the latest.")]
    [SerializeField] Vector2 openAfter = new Vector2(10f, 60f);
    [Tooltip("It waits until you are this close.")]
    [SerializeField] float hearingDistance = 6f;
    [SerializeField] float openSeconds = 5f;
    [Tooltip("How far it swings, as a share of the way: some only come ajar.")]
    [SerializeField] Vector2 openShare = new Vector2(0.35f, 1f);

    float[] openAt;

    void Awake()
    {
        openAt = new float[doors.Length];
        for (int i = 0; i < openAt.Length; i++)
            openAt[i] = float.PositiveInfinity;
        loop.NightFalls += OnNightFalls;
    }

    void OnDestroy() => loop.NightFalls -= OnNightFalls;

    void OnNightFalls()
    {
        for (int i = 0; i < doors.Length; i++)
        {
            openAt[i] = float.PositiveInfinity;
            if (loop.Night < fromNight)
                continue;
            doors[i].ShutQuietly();
            if (doors[i].IsShut && Random.value < openChance)
                openAt[i] = Time.time + Random.Range(openAfter.x, openAfter.y);
        }
    }

    void Update()
    {
        if (loop.CurrentPhase != NightLoop.Phase.Night)
            return;
        float now = Time.time;
        for (int i = 0; i < doors.Length; i++)
        {
            if (now < openAt[i])
                continue;
            if (!doors[i].IsShut)
            {
                // You got there first.
                openAt[i] = float.PositiveInfinity;
                continue;
            }
            Vector3 toDoor = doors[i].Hinge - player.position;
            toDoor.y = 0f;
            if (toDoor.magnitude > hearingDistance)
                continue;
            doors[i].OpenBySelf(openSeconds, Random.Range(openShare.x, openShare.y));
            openAt[i] = float.PositiveInfinity;
        }
    }
}
