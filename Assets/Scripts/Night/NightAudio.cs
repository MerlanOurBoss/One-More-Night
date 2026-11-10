using UnityEngine;

/// <summary>Everything you hear: room tone by day, the drone by night, breathing near an anomaly, and the things behind the walls.</summary>
public class NightAudio : MonoBehaviour
{
    [Header("Scene")]
    [SerializeField] NightLoop loop;
    [SerializeField] Transform player;
    [SerializeField] Transform door;
    [SerializeField] Transform voicesPoint;

    [Header("Sources")]
    [SerializeField] AudioSource roomTone;
    [SerializeField] AudioSource nightDrone;
    [SerializeField] AudioSource breathing;
    [SerializeField] AudioSource camera2D;
    [SerializeField] AudioSource steps2D;
    [SerializeField] AudioSource world;

    [Header("Clips")]
    [SerializeField] AudioClip shutter;
    [SerializeField] AudioClip shutterEmpty;
    [SerializeField] AudioClip vanish;
    [SerializeField] AudioClip wrong;
    [SerializeField] AudioClip stinger;
    [SerializeField] AudioClip stingerLong;
    [SerializeField] AudioClip knock;
    [SerializeField] AudioClip creak;
    [SerializeField] AudioClip overhead;
    [SerializeField] AudioClip mutter;
    [SerializeField] AudioClip outside;
    [SerializeField] AudioClip paper;
    [SerializeField] AudioClip doorOpen;
    [SerializeField] AudioClip doorClose;
    [SerializeField] AudioClip[] footsteps;

    [Header("Mix")]
    [SerializeField] float roomToneDay = 0.35f;
    [SerializeField] float roomToneNight = 0.2f;
    [SerializeField] float droneNight = 0.7f;
    [SerializeField] float fadePerSecond = 0.4f;
    [SerializeField] float breathingRange = 2.5f;
    [SerializeField] float breathingLoudest = 0.8f;

    [Header("Night events")]
    [SerializeField] float eventEvery = 16f;
    [SerializeField] float eventEveryPerNight = -2f;
    [SerializeField] float eventEveryMin = 7f;
    [SerializeField] float eventRandomness = 0.5f;

    [Header("Footsteps")]
    [SerializeField] float stepLength = 0.8f;
    [SerializeField] float stepVolume = 0.45f;

    [Header("Steps behind you: someone runs up and stops at your back")]
    [Tooltip("A 3D source of its own, moved step by step.")]
    [SerializeField] AudioSource stalker;
    [SerializeField] int stalkerFromNight = 2;
    [Tooltip("The chance that a night event is this one. At most once a night.")]
    [SerializeField, Range(0f, 1f)] float stalkerChance = 0.25f;
    [Tooltip("Only once you have stood still this long: they must not pass for your own.")]
    [SerializeField] float stalkerAfterStill = 1.5f;
    [SerializeField] int stalkerSteps = 9;
    [Tooltip("Seconds between the first steps, and between the last ones.")]
    [SerializeField] Vector2 stalkerGap = new Vector2(0.6f, 0.22f);
    [SerializeField] float stalkerStartDistance = 6f;
    [SerializeField] float stalkerStopDistance = 0.7f;
    [Tooltip("Lower than yours: heavier.")]
    [SerializeField] float stalkerPitch = 0.82f;
    [SerializeField] Vector2 stalkerVolume = new Vector2(0.35f, 1f);

    Vector3 lastPlayerPosition;
    float stillSince;
    bool stalking;
    int stalkedNight = -1;
    float walked;
    float nextEventTime;
    NightLoop.Phase lastPhase;

    void Start()
    {
        lastPlayerPosition = player.position;
        foreach (AudioSource source in new[] { roomTone, nightDrone, breathing })
        {
            source.volume = 0f;
            source.Play();
        }
    }

    void Update()
    {
        NightLoop.Phase phase = loop.CurrentPhase;
        Mix(phase);
        Footsteps();

        if (phase == NightLoop.Phase.Night)
        {
            if (lastPhase != NightLoop.Phase.Night)
                ScheduleEvent();
            if (Time.time >= nextEventTime)
            {
                PlayEvent();
                ScheduleEvent();
            }
        }
        lastPhase = phase;
    }

    void Mix(NightLoop.Phase phase)
    {
        // During a fade the room holds its breath.
        float tone = phase == NightLoop.Phase.Day ? roomToneDay : phase == NightLoop.Phase.Night ? roomToneNight : 0f;
        // The drone starts leaking into the day as the nights pile up.
        float drone = phase == NightLoop.Phase.Night ? droneNight : phase == NightLoop.Phase.Day ? droneNight * loop.Lateness : 0f;
        float step = fadePerSecond * Time.deltaTime;
        roomTone.volume = Mathf.MoveTowards(roomTone.volume, tone, step);
        nightDrone.volume = Mathf.MoveTowards(nightDrone.volume, drone, step);

        float close = phase == NightLoop.Phase.Transition ? 0f : 1f - Mathf.Clamp01(loop.NearestAnomalyDistance / breathingRange);
        breathing.volume = Mathf.MoveTowards(breathing.volume, close * close * breathingLoudest, step);
    }

    void Footsteps()
    {
        Vector3 moved = player.position - lastPlayerPosition;
        moved.y = 0f;
        lastPlayerPosition = player.position;

        if (moved.sqrMagnitude > 0.0001f)
            stillSince = Time.time;

        // A teleport is not a step.
        if (moved.magnitude > 0.5f)
            return;
        walked += moved.magnitude;
        if (walked >= stepLength)
        {
            walked = 0f;
            steps2D.pitch = Random.Range(0.92f, 1.08f);
            steps2D.PlayOneShot(footsteps[Random.Range(0, footsteps.Length)], stepVolume);
        }
    }

    void ScheduleEvent()
    {
        float every = Mathf.Max(eventEveryMin, eventEvery + eventEveryPerNight * (loop.Night - 1));
        nextEventTime = Time.time + every * Random.Range(1f - eventRandomness, 1f + eventRandomness);
    }

    void PlayEvent()
    {
        if (stalker != null && !stalking && loop.Night >= stalkerFromNight && stalkedNight != loop.Night
            && Time.time - stillSince >= stalkerAfterStill && Random.value < stalkerChance
            && FindStalkerStart(out Vector3 from, out Vector3 away))
        {
            StartCoroutine(StepsBehind(from, away));
            return;
        }

        switch (Random.Range(0, 4))
        {
            case 0: PlayInWorld(knock, door.position); break;
            case 1: PlayInWorld(creak, door.position); break;
            case 2: PlayInWorld(overhead, player.position + Vector3.up * 2.6f); break;
            default: PlayInWorld(mutter, voicesPoint.position); break;
        }
    }

    /// <summary>
    /// Where they start: as far behind you as the flat goes, or a little to the side, on its floor.
    /// Walls do not stop the sound, so it may well be the next room.
    /// </summary>
    public bool FindStalkerStart(out Vector3 from, out Vector3 away)
    {
        Vector3 back = -player.forward;
        back.y = 0f;
        back.Normalize();
        for (float distance = stalkerStartDistance; distance >= stalkerStopDistance + 2f; distance -= 0.5f)
        {
            // Straight behind first; in a corner, from the side.
            foreach (float turn in new[] { 0f, 30f, -30f, 60f, -60f, 90f, -90f, 120f, -120f })
            {
                away = Quaternion.Euler(0f, turn, 0f) * back;
                from = player.position + away * distance;
                // Under the ceiling, straight down onto a room's floor: not into furniture, not out on the balcony.
                if (Physics.Raycast(new Vector3(from.x, 2f, from.z), Vector3.down, out RaycastHit floor, 2.5f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
                    && floor.point.y < 0.05f && floor.collider.name.StartsWith("Floor_"))
                    return true;
            }
        }
        from = away = Vector3.zero;
        return false;
    }

    /// <summary>Far off behind you, then faster and louder, the last one right at your back. Then nothing.</summary>
    public System.Collections.IEnumerator StepsBehind(Vector3 from, Vector3 away)
    {
        stalking = true;
        stalkedNight = loop.Night;
        for (int i = 0; i < stalkerSteps && loop.CurrentPhase == NightLoop.Phase.Night; i++)
        {
            float t = i / (stalkerSteps - 1f);
            // It ends at your back where you stand now, along the way it came.
            Vector3 to = player.position + away * stalkerStopDistance;
            Vector3 at = Vector3.Lerp(from, to, t);
            at.y = 0.05f;
            stalker.transform.position = at;
            stalker.pitch = stalkerPitch * Random.Range(0.96f, 1.04f);
            stalker.PlayOneShot(footsteps[Random.Range(0, footsteps.Length)], Mathf.Lerp(stalkerVolume.x, stalkerVolume.y, t * t));
            yield return new WaitForSeconds(Mathf.Lerp(stalkerGap.x, stalkerGap.y, t));
        }
        stalking = false;
    }

    void PlayInWorld(AudioClip clip, Vector3 position)
    {
        world.transform.position = position;
        world.PlayOneShot(clip);
    }

    public void PlayShutter() => camera2D.PlayOneShot(shutter);
    public void PlayShutterEmpty() => camera2D.PlayOneShot(shutterEmpty);
    public void PlayVanish() => camera2D.PlayOneShot(vanish);
    public void PlayWrong() => camera2D.PlayOneShot(wrong);
    public void PlayStinger() => camera2D.PlayOneShot(stinger);
    public void PlayStingerLong() => camera2D.PlayOneShot(stingerLong);
    public void PlayDoor() => PlayInWorld(creak, door.position);
    public void PlayOutside() => camera2D.PlayOneShot(outside);
    public void StopCamera() => camera2D.Stop();
    public void PlayPaper() => camera2D.PlayOneShot(paper);
    public void PlayDoorOpen() => camera2D.PlayOneShot(doorOpen);
    public void PlayDoorClose() => camera2D.PlayOneShot(doorClose);
    public void PlayCreakAt(Vector3 position) => PlayInWorld(creak, position);
    /// <summary>A creak that stays where it began, however many others start meanwhile.</summary>
    public void PlayCreakApart(Vector3 position) => AudioSource.PlayClipAtPoint(creak, position);
    public void PlayKnock() => PlayInWorld(knock, door.position);
    public void PlayShutterAt(Vector3 position) => PlayInWorld(shutter, position);
}
