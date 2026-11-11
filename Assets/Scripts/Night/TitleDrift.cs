using UnityEngine;

/// <summary>Behind the title the view is not still: it looks slowly around the bedroom, the way someone does who cannot sleep.</summary>
public class TitleDrift : MonoBehaviour
{
    [SerializeField] NightLoop loop;
    [SerializeField] GameObject titleScreen;
    [SerializeField] Transform view;
    [Tooltip("Degrees it turns either way, left and right.")]
    [SerializeField] float yaw = 7f;
    [Tooltip("Degrees it tips either way, up and down.")]
    [SerializeField] float pitch = 2.5f;
    [Tooltip("Seconds for one look left and right; up and down goes at its own, unrelated pace.")]
    [SerializeField] float period = 26f;
    [Tooltip("How far it leans in and back, in metres.")]
    [SerializeField] float lean = 0.06f;

    bool drifting;
    Vector3 basePosition;
    Quaternion baseRotation;
    float startedAt;

    // After everything else has moved the view this frame, so that nothing else's change is lost.
    void LateUpdate()
    {
        bool shown = titleScreen.activeSelf && !loop.Started;
        if (shown && !drifting)
        {
            basePosition = view.localPosition;
            baseRotation = view.localRotation;
            startedAt = Time.time;
            drifting = true;
        }
        if (!drifting)
            return;
        if (!shown)
        {
            Stop();
            return;
        }

        float t = Time.time - startedAt;
        // Eased in from rest, so the first frame is exactly where the player stands.
        float ease = Mathf.Clamp01(t / 4f);
        float turn = Mathf.Sin(t * 2f * Mathf.PI / period) * yaw * ease;
        float tip = Mathf.Sin(t * 2f * Mathf.PI / (period * 0.63f) + 1.3f) * pitch * ease;
        view.localRotation = Quaternion.Euler(tip, turn, 0f) * baseRotation;
        view.localPosition = basePosition + Vector3.forward * (Mathf.Sin(t * 2f * Mathf.PI / (period * 1.4f)) * lean * ease);
    }

    /// <summary>Back exactly to where the player stands: before the intro or the first day takes the view.</summary>
    public void Stop()
    {
        if (!drifting)
            return;
        view.localPosition = basePosition;
        view.localRotation = baseRotation;
        drifting = false;
    }
}
