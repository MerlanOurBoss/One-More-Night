using UnityEngine;

/// <summary>The first time you catch sight of her, she looks at you, your head jerks round and the view closes in on her face as the sound hits. Once for each time she comes.</summary>
public class GhostScare : MonoBehaviour
{
    [SerializeField] Anomaly anomaly;
    [SerializeField] HeadWatch head;
    [SerializeField] NightLoop loop;
    [SerializeField] FirstPersonController player;
    [SerializeField] NightAudio sound;
    [Tooltip("Farther than this she is lost in the fog.")]
    [SerializeField] float maxDistance = 5f;
    [Tooltip("How much of the screen's height her head takes at the closest, whatever the distance.")]
    [SerializeField, Range(0.2f, 1.5f)] float faceFills = 1f;
    [SerializeField] float turnSeconds = 0.16f;
    [SerializeField] float holdSeconds = 0.7f;
    [SerializeField] float releaseSeconds = 0.3f;

    bool done;

    void Update()
    {
        if (!anomaly.Active)
        {
            done = false;
            return;
        }
        // Frozen: at the computer, on the phone, reading. She can wait until you look up.
        if (done || !loop.Started || loop.CurrentPhase == NightLoop.Phase.Transition || player.Frozen || player.Whipping)
            return;
        if (!head.isActiveAndEnabled || !head.Seen())
            return;

        Renderer face = head.GetComponent<Renderer>();
        if (Vector3.Distance(player.transform.position, face.bounds.center) > maxDistance)
            return;

        done = true;
        head.LookAtEyeNow();
        // The mesh runs down the neck, so the face is above the middle of it.
        Vector3 eyes = face.bounds.center + Vector3.up * (face.bounds.size.y * 0.15f);
        player.WhipTo(eyes, face.bounds.size.y / faceFills, turnSeconds, holdSeconds, releaseSeconds);
        sound.PlayStinger();
    }
}
