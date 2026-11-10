using UnityEngine;

/// <summary>An inside door that opens and closes on its hinge. Room meshes are baked in world space, so it turns around a given point.</summary>
[RequireComponent(typeof(Collider))]
public class DoorSwing : MonoBehaviour
{
    [SerializeField] Transform player;
    [SerializeField] NightAudio sound;

    [Header("Door, as it stands in the model: open")]
    [SerializeField] Vector3 hinge;
    [Tooltip("Which way the door points from its hinge. 0 is +X, 90 is +Z.")]
    [SerializeField] float modelledAngle;
    [SerializeField] float width = 0.8f;
    [Tooltip("Turn from open to closed, in degrees around Y.")]
    [SerializeField] float closedYaw = -90f;

    [SerializeField] float degreesPerSecond = 120f;
    [Tooltip("The door waits rather than sweep through anyone standing closer than this.")]
    [SerializeField] float playerClearance = 0.34f;

    Vector3 homePosition;
    Quaternion homeRotation;
    float yaw;
    float targetYaw;
    float speed;

    public bool IsOpen => targetYaw == 0f;
    /// <summary>All the way shut, and staying so.</summary>
    public bool IsShut => yaw == closedYaw && targetYaw == closedYaw;
    public Vector3 Hinge => hinge;

    void Awake()
    {
        homePosition = transform.position;
        homeRotation = transform.rotation;
        speed = degreesPerSecond;
    }

    /// <summary>Shut while nobody can see, in the dark between day and night. Not onto anyone standing in the way.</summary>
    public void ShutQuietly()
    {
        if (HitsPlayer(closedYaw))
            return;
        yaw = targetYaw = closedYaw;
        Apply();
    }

    /// <summary>Swings open by itself, slowly, this share of the way, with a creak.</summary>
    public void OpenBySelf(float seconds, float share)
    {
        targetYaw = closedYaw * (1f - share);
        speed = Mathf.Abs(targetYaw - yaw) / Mathf.Max(0.1f, seconds);
        sound.PlayCreakApart(GetComponent<Renderer>().bounds.center);
    }

    public void Toggle()
    {
        speed = degreesPerSecond;
        if (IsOpen)
        {
            targetYaw = closedYaw;
            sound.PlayDoorClose();
        }
        else
        {
            targetYaw = 0f;
            sound.PlayDoorOpen();
        }
    }

    /// <summary>A new run: standing open, as the flat was left.</summary>
    public void Restore()
    {
        targetYaw = 0f;
        yaw = 0f;
        speed = degreesPerSecond;
        Apply();
    }

    void Update()
    {
        if (yaw == targetYaw)
            return;

        float next = Mathf.MoveTowards(yaw, targetYaw, speed * Time.deltaTime);
        if (HitsPlayer(next))
            return;
        yaw = next;
        Apply();
    }

    void Apply()
    {
        Quaternion turn = Quaternion.Euler(0f, yaw, 0f);
        transform.rotation = turn * homeRotation;
        transform.position = hinge + turn * (homePosition - hinge);
    }

    bool HitsPlayer(float atYaw)
    {
        float angle = modelledAngle * Mathf.Deg2Rad;
        Vector3 along = Quaternion.Euler(0f, atYaw, 0f) * new Vector3(Mathf.Cos(angle), 0f, Mathf.Sin(angle));
        Vector3 toPlayer = player.position - hinge;
        toPlayer.y = 0f;
        Vector3 nearest = along * Mathf.Clamp(Vector3.Dot(toPlayer, along), 0f, width);
        return (toPlayer - nearest).sqrMagnitude < playerClearance * playerClearance;
    }
}
