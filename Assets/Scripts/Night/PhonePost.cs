using System.Collections;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// The phone on the hall wall. Each morning the client rings with the night's task.
/// From the second night it sometimes rings in the dark too, and it is not the client.
/// </summary>
[RequireComponent(typeof(Collider))]
public class PhonePost : MonoBehaviour
{
    [SerializeField] NightLoop loop;
    [SerializeField] FirstPersonController player;
    [SerializeField] NightAudio sound;
    [SerializeField] AudioSource bell;
    [SerializeField] AudioSource earpiece;
    [SerializeField] AudioClip voice;
    [SerializeField] AudioClip breath;
    [SerializeField] AudioClip hiss;
    [SerializeField] Text caption;

    [Header("When it rings")]
    [SerializeField] Vector2 morningRingAfter = new Vector2(6f, 15f);
    [SerializeField] int nightCallsFromNight = 2;
    [SerializeField] float nightCallChance = 0.4f;
    [SerializeField] Vector2 nightRingAfter = new Vector2(20f, 55f);
    [SerializeField] float ringsFor = 14f;
    [SerializeField] float lineShownFor = 3.2f;

    enum Call { None, Client, Breathing, Neighbour, Her }

    Call pending = Call.None;
    float ringAt;
    float ringUntil;
    int dayRung = -1;
    int nightRung = -1;
    // Not a phase the game starts in, so the first day after the title gets its call.
    NightLoop.Phase lastPhase = NightLoop.Phase.Transition;

    public bool Ringing { get; private set; }
    public bool Talking { get; private set; }

    void Awake()
    {
        caption.gameObject.SetActive(false);
        bell.loop = true;
        bell.Stop();
    }

    /// <summary>A new run: nobody has called yet.</summary>
    public void Clear()
    {
        StopAllCoroutines();
        pending = Call.None;
        Ringing = false;
        Talking = false;
        dayRung = -1;
        nightRung = -1;
        lastPhase = NightLoop.Phase.Transition;
        bell.Stop();
        earpiece.Stop();
        caption.gameObject.SetActive(false);
    }

    void Update()
    {
        if (!loop.Started)
            return;
        NightLoop.Phase phase = loop.CurrentPhase;
        if (phase != lastPhase)
        {
            lastPhase = phase;
            Schedule(phase);
        }
        if (Talking)
            return;

        if (!Ringing && pending != Call.None && Time.time >= ringAt && phase != NightLoop.Phase.Transition)
        {
            Ringing = true;
            ringUntil = Time.time + ringsFor;
            bell.Play();
        }
        if (Ringing && (Time.time >= ringUntil || phase == NightLoop.Phase.Transition))
            StopRinging();
    }

    void Schedule(NightLoop.Phase phase)
    {
        if (phase == NightLoop.Phase.Day && dayRung != loop.Night)
        {
            dayRung = loop.Night;
            pending = Call.Client;
            ringAt = Time.time + Random.Range(morningRingAfter.x, morningRingAfter.y);
        }
        else if (phase == NightLoop.Phase.Night && nightRung != loop.Night)
        {
            nightRung = loop.Night;
            pending = loop.Night >= nightCallsFromNight && Random.value < nightCallChance ? PickNightCall() : Call.None;
            ringAt = Time.time + Random.Range(nightRingAfter.x, nightRingAfter.y);
        }
    }

    Call PickNightCall()
    {
        float roll = Random.value;
        if (loop.Night >= 4 && roll < 0.3f)
            return Call.Her;
        return roll < 0.65f ? Call.Breathing : Call.Neighbour;
    }

    void StopRinging()
    {
        Ringing = false;
        pending = Call.None;
        bell.Stop();
    }

    public void Answer()
    {
        if (!Ringing)
            return;
        Call call = pending;
        StopRinging();
        StartCoroutine(Talk(call));
    }

    IEnumerator Talk(Call call)
    {
        Talking = true;
        player.Frozen = true;
        sound.PlayShutterEmpty();
        yield return new WaitForSeconds(0.4f);

        switch (call)
        {
            case Call.Client:
                yield return Say(voice, 0.8f, "Это заказчик.", "Этой ночью нужны снимки " + loop.TaskRoomName + ". Заплатим вдвое.");
                break;
            case Call.Breathing:
                yield return Say(breath, 1f, "[кто-то дышит в трубку]");
                break;
            case Call.Neighbour:
                yield return Say(voice, 0.55f, "Откройте, пожалуйста. Я соседка.", "Мне очень нужно войти.");
                break;
            case Call.Her:
                yield return Say(hiss, 0.5f, "[помехи]", "...уходи сегодня...");
                break;
        }

        sound.PlayShutterEmpty();
        caption.gameObject.SetActive(false);
        earpiece.Stop();
        player.Frozen = false;
        Talking = false;

        // The neighbour does not go away.
        if (call == Call.Neighbour)
        {
            yield return new WaitForSeconds(2f);
            sound.PlayKnock();
        }
    }

    IEnumerator Say(AudioClip clip, float volume, params string[] lines)
    {
        earpiece.clip = clip;
        earpiece.volume = volume;
        earpiece.loop = true;
        earpiece.Play();
        caption.gameObject.SetActive(true);
        foreach (string line in lines)
        {
            caption.text = line;
            yield return new WaitForSeconds(lineShownFor);
        }
    }
}
