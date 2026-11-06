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

    Vector3 lastPlayerPosition;
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
        switch (Random.Range(0, 4))
        {
            case 0: PlayInWorld(knock, door.position); break;
            case 1: PlayInWorld(creak, door.position); break;
            case 2: PlayInWorld(overhead, player.position + Vector3.up * 2.6f); break;
            default: PlayInWorld(mutter, voicesPoint.position); break;
        }
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
    public void PlayDoor() => PlayInWorld(creak, door.position);
    public void PlayOutside() => camera2D.PlayOneShot(outside);
    public void StopCamera() => camera2D.Stop();
    public void PlayPaper() => camera2D.PlayOneShot(paper);
    public void PlayDoorOpen() => camera2D.PlayOneShot(doorOpen);
    public void PlayDoorClose() => camera2D.PlayOneShot(doorClose);
    public void PlayCreakAt(Vector3 position) => PlayInWorld(creak, position);
    public void PlayKnock() => PlayInWorld(knock, door.position);
    public void PlayShutterAt(Vector3 position) => PlayInWorld(shutter, position);
}
