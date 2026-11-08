using UnityEngine;

/// <summary>Makes an appliance live along with its anomaly: it hums or falls silent, spins, breathes or glows, and creaks when its stage grows.
/// By day an active anomaly just stands there; all of this happens at night.</summary>
public class ApplianceLife : MonoBehaviour
{
    [Header("Scene")]
    [SerializeField] Anomaly anomaly;
    [SerializeField] NightLoop loop;
    [SerializeField] Transform player;
    [Tooltip("The player's eye: what it can see decides when a sneaking door moves.")]
    [SerializeField] Camera view;

    [Header("Sound")]
    [Tooltip("Loops. Silent during the fades between day and night.")]
    [SerializeField] AudioSource hum;
    [Tooltip("While nothing is wrong, day and night. A fridge hums; once its anomaly starts, it stops.")]
    [SerializeField] float calmVolume;
    [Tooltip("At night, at each stage, from the first.")]
    [SerializeField] float[] stageVolumes = { 0f };
    [SerializeField] float[] stagePitches = { 1f };
    [SerializeField] float fadePerSecond = 0.6f;
    [Tooltip("It stops when you come this close, and goes on when you leave. 0: never.")]
    [SerializeField] float stopsWithin;

    [Header("One-shots")]
    [Tooltip("Plays a few seconds into the night after the stage has grown: you hear something, then go and look.")]
    [SerializeField] AudioClip stageClip;
    [SerializeField] float stageClipVolume = 0.7f;
    [SerializeField] int stageClipFromStage = 1;
    [Tooltip("Plays once each time you come within range while the anomaly is active at night.")]
    [SerializeField] AudioClip approachClip;
    [SerializeField] float approachRange = 2.6f;
    [Tooltip("The same clip with nothing wrong: otherwise it would tell you for free that this is worth a frame of film.")]
    [Range(0f, 1f)]
    [SerializeField] float approachFalseChance;

    [Header("False alarms")]
    [Tooltip("At night, while its own anomaly is calm: on average every this many seconds. 0: never.")]
    [SerializeField] float falseAlarmEvery;
    [SerializeField] AudioClip falseAlarmClip;
    [SerializeField] float falseAlarmVolume = 0.7f;
    [Tooltip("Seconds its calm hum drops out for, between these two. 0: it does not.")]
    [SerializeField] Vector2 falseSilence;

    [Header("Spin")]
    [SerializeField] Transform spinner;
    [SerializeField] Vector3 spinAxis = Vector3.right;
    [Tooltip("Degrees per second at each stage, from the first.")]
    [SerializeField] float[] spinSpeeds = { 0f };
    [SerializeField] float spinEasePerSecond = 180f;

    [Header("Breathing")]
    [SerializeField] Transform breather;
    [SerializeField] Vector3 breatheAxis = Vector3.forward;
    [SerializeField] float breatheDegrees = 10f;
    [SerializeField] float breatheSeconds = 5f;

    [Header("Glow")]
    [Tooltip("Gets a copy of its material with this emission, flickering.")]
    [SerializeField] Renderer glow;
    [SerializeField] Color glowColor = new Color(0.42f, 0.27f, 0.1f);
    [SerializeField] Light glowLight;

    static readonly int EmissionId = Shader.PropertyToID("_Emission");

    // All the appliances share this, so that their false alarms never pile up into something that feels like a pattern.
    const float FalseAlarmGap = 12f;
    static float lastFalseAlarm = float.NegativeInfinity;
    static readonly Plane[] Frustum = new Plane[6];

    TransformAnomaly sneaky;
    bool waiting;
    bool sawIt;
    float lastSeen;
    float lookAwayDelay;
    float giveUpAt;

    Quaternion breatherBase;
    Material glowMaterial;
    float glowLightIntensity;
    float spinSpeed;
    float stageClipTime = float.PositiveInfinity;
    float nextFalseAlarm = float.PositiveInfinity;
    float silentUntil;
    int lastStage;
    bool wasClose;

    void Awake()
    {
        sneaky = anomaly as TransformAnomaly;
        if (sneaky != null && !sneaky.Sneaks)
            sneaky = null;
        if (hum != null)
        {
            hum.loop = true;
            hum.volume = 0f;
        }
        if (glow != null)
            glowMaterial = glow.material;
        if (glowLight != null)
        {
            glowLightIntensity = glowLight.intensity;
            glowLight.enabled = false;
        }
    }

    void OnDestroy()
    {
        if (glowMaterial != null)
            Destroy(glowMaterial);
    }

    void Update()
    {
        int stage = anomaly.Stage;
        bool night = loop.CurrentPhase == NightLoop.Phase.Night;
        Sneak(stage, night);
        // A door still waiting to move keeps up appearances. Only a hum that should stop has already stopped.
        bool alive = stage > 0 && night && !(sneaky != null && sneaky.Pending);
        float distance = Vector3.Distance(player.position, transform.position);
        bool stopped = stopsWithin > 0f && distance < stopsWithin;

        if (stage != lastStage)
        {
            if (stage > lastStage && stage >= stageClipFromStage && sneaky == null)
                stageClipTime = float.NegativeInfinity;   // armed: it starts counting when the night does
            else if (stage == 0)
                stageClipTime = float.PositiveInfinity;
            if (stage > 0 && breather != null)
                breatherBase = breather.localRotation;
            lastStage = stage;
        }

        FalseAlarms(stage, night);
        Sound(stage, alive, stopped);
        OneShots(stage, night, distance);
        Spin(stage, alive && !stopped);
        Breathe(alive);
        Glow(alive);
    }

    // You look: it is shut. You look away, it creaks, you look back: it is open. If you never came, it opens anyway and you hear it from afar.
    void Sneak(int stage, bool night)
    {
        if (sneaky == null || !sneaky.Pending)
        {
            waiting = false;
            return;
        }
        if (!night)
            return;

        float now = Time.time;
        if (!waiting)
        {
            waiting = true;
            sawIt = false;
            lookAwayDelay = Random.Range(1.5f, 4f);
            giveUpAt = now + Random.Range(15f, 40f);
        }

        if (Seen())
        {
            sawIt = true;
            lastSeen = now;
            return;
        }
        if (sawIt ? now - lastSeen >= lookAwayDelay : now >= giveUpAt)
        {
            sneaky.Reveal();
            if (stageClip != null && stage >= stageClipFromStage)
                PlayOneShot(stageClip, stageClipVolume);
        }
    }

    bool Seen()
    {
        Bounds bounds = anomaly.Bounds;
        GeometryUtility.CalculateFrustumPlanes(view, Frustum);
        if (!GeometryUtility.TestPlanesAABB(Frustum, bounds))
            return false;
        Vector3 eye = view.transform.position;
        Vector3 toCenter = bounds.center - eye;
        bool blocked = Physics.Raycast(eye, toCenter.normalized, out RaycastHit hit, toCenter.magnitude, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
            && !anomaly.Owns(hit.collider);
        return !blocked;
    }

    void FalseAlarms(int stage, bool night)
    {
        if (!night || stage > 0)
        {
            silentUntil = 0f;
            nextFalseAlarm = float.PositiveInfinity;
            return;
        }
        if (falseAlarmEvery <= 0f)
            return;

        float now = Time.time;
        if (float.IsPositiveInfinity(nextFalseAlarm))
            nextFalseAlarm = now + falseAlarmEvery * Random.Range(0.5f, 1.5f);
        else if (now >= nextFalseAlarm)
        {
            if (now >= lastFalseAlarm && now - lastFalseAlarm < FalseAlarmGap)
                nextFalseAlarm = now + Random.Range(3f, 8f);
            else
            {
                FireFalseAlarm();
                nextFalseAlarm = now + falseAlarmEvery * Random.Range(0.5f, 1.5f);
            }
        }
    }

    void FireFalseAlarm()
    {
        lastFalseAlarm = Time.time;
        if (falseAlarmClip != null)
            PlayOneShot(falseAlarmClip, falseAlarmVolume);
        if (falseSilence.y > 0f)
            silentUntil = Time.time + Random.Range(falseSilence.x, falseSilence.y);
    }

    void Sound(int stage, bool alive, bool stopped)
    {
        if (hum == null)
            return;
        float target;
        if (loop.CurrentPhase == NightLoop.Phase.Transition)
            target = 0f;
        else if (stage == 0)
            target = Time.time < silentUntil ? 0f : calmVolume;
        else
            target = alive && !stopped ? At(stageVolumes, stage) : 0f;

        if (stage > 0)
            hum.pitch = At(stagePitches, stage);
        else
            hum.pitch = 1f;
        if (target > 0f && !hum.isPlaying)
            hum.Play();
        hum.volume = Mathf.MoveTowards(hum.volume, target, fadePerSecond * Time.deltaTime);
        if (target <= 0f && hum.volume <= 0f && hum.isPlaying)
            hum.Stop();
    }

    void OneShots(int stage, bool night, float distance)
    {
        bool alive = stage > 0 && night;
        if (stageClip != null && alive)
        {
            if (float.IsNegativeInfinity(stageClipTime))
                stageClipTime = Time.time + Random.Range(2f, 6f);
            else if (Time.time >= stageClipTime)
            {
                stageClipTime = float.PositiveInfinity;
                PlayOneShot(stageClip, stageClipVolume);
            }
        }

        bool close = distance < approachRange;
        if (approachClip != null && night && close && !wasClose && (stage > 0 || Random.value < approachFalseChance))
            PlayOneShot(approachClip, 0.8f);
        wasClose = close;
    }

    // Its own short-lived source: the fall-off is gentle, so this is heard from the next room too. That is the point.
    void PlayOneShot(AudioClip clip, float volume) => AudioSource.PlayClipAtPoint(clip, anomaly.Center, volume);

    void Spin(int stage, bool running)
    {
        if (spinner == null)
            return;
        float target = running && stage > 0 ? At(spinSpeeds, stage) : 0f;
        spinSpeed = Mathf.MoveTowards(spinSpeed, target, spinEasePerSecond * Time.deltaTime);
        spinner.Rotate(spinAxis, spinSpeed * Time.deltaTime, Space.Self);
    }

    void Breathe(bool alive)
    {
        if (breather == null || anomaly.Stage == 0)
            return;
        float angle = alive ? Mathf.Sin(Time.time * 2f * Mathf.PI / breatheSeconds) * breatheDegrees : 0f;
        breather.localRotation = breatherBase * Quaternion.AngleAxis(angle, breatheAxis);
    }

    void Glow(bool alive)
    {
        if (glowMaterial == null)
            return;
        // Steady, with a sag now and then, like a tube about to go.
        float flicker = 0.8f + 0.2f * Mathf.PerlinNoise(Time.time * 7f, 0.3f);
        if (Mathf.PerlinNoise(Time.time * 1.3f, 5.1f) > 0.72f)
            flicker *= 0.35f;
        glowMaterial.SetColor(EmissionId, alive ? glowColor * flicker : Color.black);
        if (glowLight != null)
        {
            glowLight.enabled = alive;
            glowLight.intensity = glowLightIntensity * flicker;
        }
    }

    static float At(float[] values, int stage) => values.Length == 0 ? 0f : values[Mathf.Min(stage, values.Length) - 1];
}
