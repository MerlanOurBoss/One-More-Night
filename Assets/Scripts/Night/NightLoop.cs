using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>One room, many nights: something changes each night. Photograph it for money; a photo of nothing costs money; a missed one grows.</summary>
public class NightLoop : MonoBehaviour
{
    public enum Phase { Day, Night, Transition }

    static readonly int EmissionId = Shader.PropertyToID("_Emission");
    static readonly int IntensityId = Shader.PropertyToID("_Intensity");

    [Header("Scene")]
    [SerializeField] FirstPersonController player;
    [SerializeField] Camera view;
    [SerializeField] Transform wakePoint;
    [SerializeField] float wakePitch = 12f;
    [SerializeField] Collider futon;
    [SerializeField] Collider door;
    [SerializeField] float reach = 2.2f;
    [SerializeField] Light lamp;
    [SerializeField] Renderer lampShade;
    [Tooltip("The glass. Glows with the sky by day, black at night.")]
    [SerializeField] Renderer windowPane;
    [SerializeField] Color skyColor = new Color(0.46f, 0.51f, 0.56f);
    [Tooltip("Daylight falling into the room from outside the window.")]
    [SerializeField] Light windowLight;
    [Tooltip("More daylight, for a home with more than one window.")]
    [SerializeField] Light[] moreWindowLights = new Light[0];
    [Tooltip("The other rooms' lights. They follow the main lamp's colour, and its brightness in the proportion they start with.")]
    [SerializeField] Light[] moreLamps = new Light[0];
    [Tooltip("The visible shaft of light and the patches it leaves on the floor.")]
    [SerializeField] Renderer windowBeam;
    [SerializeField] PS1Globals look;
    [SerializeField] NightAudio sound;
    [SerializeField] PhotoPrint photoPrint;
    [SerializeField] NoteCollection notes;
    [SerializeField] SafeLock safeLock;
    [SerializeField] DoorSwing[] insideDoors = new DoorSwing[0];
    [SerializeField] ComputerDesk desk;
    [SerializeField] DoorPeephole peephole;
    [SerializeField] PhonePost phone;

    [Header("Ordering film from the computer")]
    [SerializeField] int filmPrice = 3000;
    [SerializeField] int filmPack = 2;

    [Header("The client's task: one room a night pays more")]
    [SerializeField] int taskMultiplier = 2;

    [Header("Fading day")]
    [Tooltip("After the first night, the day lasts this long, then the night starts by itself.")]
    [SerializeField] float dayLength = 150f;
    [Tooltip("How much daylight is left at the very end of a day.")]
    [SerializeField, Range(0f, 1f)] float dayEndsAt = 0.25f;
    [SerializeField] ControlHints hints;
    [SerializeField] GameObject titleScreen;

    [Header("Anomalies")]
    [SerializeField] Anomaly[] anomalies;
    [SerializeField] int reportReward = 10000;
    [SerializeField] int reportRewardPerNight = 2000;
    [SerializeField] int falseReportFine = 5000;
    [Tooltip("What the client pays extra for a photo with her on it. She comes a step closer for it.")]
    [SerializeField] int ghostReward = 8000;
    [SerializeField] int secondAnomalyFromNight = 3;
    [SerializeField] float secondAnomalyChance = 0.5f;

    [Header("Photo camera")]
    [SerializeField] GameObject viewfinder;
    [Tooltip("The part of the view that counts as being in the photo, as viewport coordinates. Matches the viewfinder corners.")]
    [SerializeField] Rect photoFrame = new Rect(0.15f, 0.12f, 0.7f, 0.76f);
    [SerializeField] float photoRange = 8f;
    [SerializeField] float photoCooldown = 0.8f;
    [SerializeField] float aimFieldOfView = 52f;
    [Tooltip("A fresh roll arrives each night. What is left over can still be used the next day.")]
    [SerializeField] int filmPerNight = 4;
    [SerializeField] Text filmText;

    [Header("World swims near an active anomaly")]
    [SerializeField] float jitterRange = 1.5f;
    [SerializeField] float jitterNear = 4f;

    [Header("HUD")]
    [SerializeField] Image fade;
    [SerializeField] Image dot;
    [SerializeField] Color dotIdle = new Color(1f, 1f, 1f, 0.2f);
    [SerializeField] Color dotActive = Color.white;
    [SerializeField] RectTransform nightBar;
    [SerializeField] RawImage hand;
    [SerializeField] Text moneyText;
    [SerializeField] Text goalText;
    [SerializeField] Text nightsText;
    [SerializeField] Color fineColor = new Color(0.8f, 0.1f, 0.1f);
    [SerializeField] GameObject lostFace;

    [Header("Money")]
    [SerializeField] int goal = 100000;
    [SerializeField] float moneyShownFor = 3f;
    [SerializeField] float nightCardShownFor = 1.5f;

    [Header("Leaving: the ending depends on when you go")]
    [Tooltip("After this night the door only leads back into the room.")]
    [SerializeField] int lastNightDoorOpens = 7;
    [Tooltip("How far the day has sunk towards the night by the last morning.")]
    [SerializeField, Range(0f, 1f)] float dayDarkening = 0.9f;
    [SerializeField] Color daylight = new Color(1f, 0.93f, 0.78f);
    [SerializeField] Color daylightText = new Color(0.16f, 0.12f, 0.08f);
    [SerializeField] float trappedLength = 40f;

    [Header("Night")]
    [SerializeField] float nightLength = 60f;
    [SerializeField] float nightLampIntensity = 2f;
    [SerializeField] float nightFogNear = 0.8f;
    [SerializeField] float nightFogFar = 5.5f;
    [SerializeField] float nightBrightness = 0.5f;

    public Phase CurrentPhase { get; private set; } = Phase.Day;
    public int Night { get; private set; } = 1;
    public int Money { get; private set; }
    public int Film { get; private set; }
    public float NearestAnomalyDistance { get; private set; } = float.PositiveInfinity;
    public Rect PhotoFrame => photoFrame;
    /// <summary>False while the title screen is up.</summary>
    public bool Started { get; private set; }
    /// <summary>Sitting at the computer.</summary>
    public bool AtDesk => desk != null && desk.Seated;
    /// <summary>Looking through the peephole.</summary>
    public bool Peeping => peephole != null && peephole.Looking;
    /// <summary>On the phone.</summary>
    public bool OnPhone => phone != null && phone.Talking;
    /// <summary>Film ordered today, delivered for the night.</summary>
    public int ExtraFilm { get; private set; }
    public int FilmPrice => filmPrice;
    public int FilmPack => filmPack;

    // The four rooms on the plan, and how the client names each one.
    static readonly string[] RoomIds = { "kitchen", "bedroom", "bath", "hall" };
    static readonly string[] RoomNames = { "на кухне", "в зале", "в ванной", "в коридоре" };
    string taskRoom;
    int taskNight = -1;

    /// <summary>Where the client wants photos tonight, as the client says it: "в зале".</summary>
    public string TaskRoomName => taskRoom == null ? "" : RoomNames[System.Array.IndexOf(RoomIds, taskRoom)];
    public string TaskText => taskNight == Night && taskRoom != null ? "ночью нужны снимки " + TaskRoomName + ", оплата вдвое" : "новых заданий нет";

    /// <summary>Whether a photo of this room, taken tonight, is the one the client asked for.</summary>
    public bool IsTaskRoom(string room) => CurrentPhase == Phase.Night && taskNight == Night && room == taskRoom;

    /// <summary>A new job each morning, for the night ahead.</summary>
    void NewTask()
    {
        taskNight = Night;
        taskRoom = RoomIds[Random.Range(0, RoomIds.Length)];
    }

    public static string RoomAt(Vector3 p)
    {
        if (p.x > 0.063f)
            return "bedroom";
        if (p.z > -0.158f)
            return "kitchen";
        if (p.x < -1.495f)
            return "bath";
        return "hall";
    }

    public bool OrderFilm()
    {
        if (Money < filmPrice)
            return false;
        Money -= filmPrice;
        ExtraFilm += filmPack;
        ShowMoneyBriefly(Color.white);
        return true;
    }
    /// <summary>Photos taken but not sent yet.</summary>
    public bool HasUnsentPhotos
    {
        get
        {
            foreach (PhotoPrint.Shot shot in photoPrint.Archive)
            {
                if (!shot.Sent)
                    return true;
            }
            return false;
        }
    }
    /// <summary>What E would do right now, or null.</summary>
    public string UsePrompt { get; private set; }
    /// <summary>0 on the first day, 1 once the door has stopped leading anywhere.</summary>
    public float Lateness => Mathf.Clamp01((Night - 1f) / lastNightDoorOpens);

    InputAction interact;
    InputAction aim;
    InputAction shutter;
    Material shade;
    Material pane;
    Material beam;
    float windowLightIntensity;
    float[] moreWindowLightIntensities;
    float[] moreLampShares;
    float dayIntensity;
    float dayFogNear;
    float dayFogFar;
    float baseJitter;
    float normalFieldOfView;
    float brightness = 1f;
    float nextPhotoTime;
    bool sleepRequested;
    bool dayTimed;
    float dayLeft;
    float dayLight = 1f;
    bool doorRequested;
    bool trapped;
    Color goalColor;
    Coroutine moneyDisplay;

    void Awake()
    {
        interact = InputSystem.actions.FindAction("Player/Interact", true);
        aim = InputSystem.actions.FindAction("Player/Aim", true);
        shutter = InputSystem.actions.FindAction("Player/Attack", true);
        normalFieldOfView = view.fieldOfView;
        shade = lampShade.material;
        pane = windowPane.material;
        beam = windowBeam.material;
        windowLightIntensity = windowLight.intensity;
        moreLampShares = new float[moreLamps.Length];
        for (int i = 0; i < moreLamps.Length; i++)
            moreLampShares[i] = moreLamps[i].intensity / lamp.intensity;
        moreWindowLightIntensities = new float[moreWindowLights.Length];
        for (int i = 0; i < moreWindowLights.Length; i++)
            moreWindowLightIntensities[i] = moreWindowLights[i].intensity;
        SetDaylight(1f);
        dayIntensity = lamp.intensity;
        dayFogNear = look.FogNear;
        dayFogFar = look.FogFar;
        baseJitter = look.Jitter;
        Film = filmPerNight;
        goalColor = goalText.color;
        NewTask();

        fade.color = Color.clear;
        nightBar.localScale = new Vector3(0f, 1f, 1f);
        moneyText.gameObject.SetActive(false);
        goalText.gameObject.SetActive(false);
        nightsText.gameObject.SetActive(false);
        ShowTitle();
    }

    void ShowTitle()
    {
        Started = false;
        titleScreen.SetActive(true);
        player.Frozen = true;
    }

    void Update()
    {
        UsePrompt = null;
        // Every frame so the lampshade follows the light, including a lamp anomaly.
        shade.SetColor(EmissionId, lamp.color * brightness);
        for (int i = 0; i < moreLamps.Length; i++)
        {
            moreLamps[i].color = lamp.color;
            moreLamps[i].intensity = lamp.intensity * moreLampShares[i];
        }
        hand.color = new Color(brightness, brightness, brightness, 1f);
        look.Jitter = JitterNearAnomalies();

        bool aiming = Started && CurrentPhase != Phase.Transition && !notes.Reading && !safeLock.Busy && !AtDesk && !Peeping && !OnPhone && aim.IsPressed();
        viewfinder.SetActive(aiming);
        hand.enabled = Started && !aiming && !AtDesk && !Peeping && !OnPhone;
        view.fieldOfView = AtDesk ? desk.FieldOfView : aiming ? aimFieldOfView : normalFieldOfView;
        filmText.text = Film.ToString();
        filmText.color = Film > 0 ? Color.white : fineColor;
        foreach (Anomaly anomaly in anomalies)
            anomaly.SetAiming(aiming);

        if (CurrentPhase == Phase.Transition)
        {
            dot.color = dotIdle;
            return;
        }

        if (!Started)
        {
            dot.color = dotIdle;
            if (interact.WasPressedThisFrame())
            {
                Started = true;
                titleScreen.SetActive(false);
                player.Frozen = false;
            }
            else if (Keyboard.current != null && Keyboard.current.escapeKey.wasPressedThisFrame)
            {
                Application.Quit();
            }
            return;
        }

        FadeTheDay();

        if (safeLock.Busy || AtDesk || Peeping || OnPhone)
        {
            dot.color = dotIdle;
            return;
        }

        if (notes.Reading)
        {
            dot.color = dotIdle;
            if (interact.WasPressedThisFrame())
                notes.Close();
            return;
        }

        Collider usable = Usable();
        dot.color = usable != null ? dotActive : dotIdle;
        UsePrompt = usable != null ? PromptFor(usable) : null;

        // The E that stood you up from the desk must not sit you straight back down.
        if (usable != null && interact.WasPressedThisFrame() && !(desk != null && desk.JustStood) && !(peephole != null && peephole.JustClosed))
            Use(usable);
        else if (aiming && shutter.WasPressedThisFrame() && Time.time >= nextPhotoTime)
        {
            if (Film > 0)
                TakePhoto();
            else
                sound.PlayShutterEmpty();
        }
    }

    float JitterNearAnomalies()
    {
        float nearest = float.PositiveInfinity;
        foreach (Anomaly anomaly in anomalies)
        {
            if (anomaly.Active)
                nearest = Mathf.Min(nearest, Vector3.Distance(view.transform.position, anomaly.Center));
        }
        NearestAnomalyDistance = nearest;
        return Mathf.Lerp(jitterNear, baseJitter, Mathf.Clamp01(nearest / jitterRange));
    }

    Collider Usable()
    {
        var ray = new Ray(view.transform.position, view.transform.forward);
        if (!Physics.Raycast(ray, out RaycastHit hit, reach, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            return null;
        bool day = CurrentPhase == Phase.Day;
        bool usable = hit.collider == futon || hit.collider.GetComponent<DoorSwing>() != null || hit.collider.GetComponent<ComputerDesk>() != null || hit.collider.GetComponent<DoorPeephole>() != null || (phone != null && hit.collider == phone.GetComponent<Collider>() && phone.Ringing) || notes.IsNote(hit.collider) || (day && safeLock.IsLocked(hit.collider)) || (hit.collider == door && (day || trapped));
        return usable ? hit.collider : null;
    }

    string PromptFor(Collider target)
    {
        DoorSwing swing = target.GetComponent<DoorSwing>();
        if (swing != null)
            return swing.IsOpen ? "закрыть дверь" : "открыть дверь";
        if (target.GetComponent<ComputerDesk>() != null)
            return "сесть за компьютер";
        if (target.GetComponent<DoorPeephole>() != null)
            return "посмотреть в глазок";
        if (phone != null && target == phone.GetComponent<Collider>())
            return "взять трубку";
        if (notes.IsNote(target))
            return "прочитать";
        if (safeLock.IsLocked(target))
            return "открыть сейф";
        if (target == door)
            return "уйти";
        return CurrentPhase == Phase.Day ? "лечь спать" : "закончить ночь";
    }

    void Use(Collider target)
    {
        hints.MarkUsed(PromptFor(target));
        DoorSwing swing = target.GetComponent<DoorSwing>();
        if (swing != null)
        {
            swing.Toggle();
            return;
        }
        ComputerDesk computer = target.GetComponent<ComputerDesk>();
        if (computer != null)
        {
            computer.Sit();
            return;
        }
        DoorPeephole hole = target.GetComponent<DoorPeephole>();
        if (hole != null)
        {
            hole.Look();
            return;
        }
        if (phone != null && target == phone.GetComponent<Collider>())
        {
            phone.Answer();
            return;
        }
        if (notes.IsNote(target))
            notes.Open();
        else if (safeLock.IsLocked(target))
            safeLock.Open();
        else if (target == door && trapped)
            doorRequested = true;
        else if (target == door)
            StartCoroutine(Leave());
        else if (CurrentPhase == Phase.Day)
            StartCoroutine(RunNight());
        else
            sleepRequested = true;
    }

    void TakePhoto()
    {
        nextPhotoTime = Time.time + photoCooldown;
        Film--;
        var photographed = new List<Anomaly>();
        foreach (Anomaly anomaly in anomalies)
        {
            if (anomaly.Active && InPhoto(anomaly))
                photographed.Add(anomaly);
        }

        // Nothing is paid yet: the client pays for the photos you send from the computer.
        photoPrint.Capture(photographed.Count, RoomAt(photographed.Count > 0 ? photographed[0].Center : view.transform.position));
        hints.PhotoTaken();
        StartCoroutine(Flash(photographed));
        sound.PlayShutter();
        if (photographed.Count > 0)
            sound.PlayVanish();
        else
            sound.PlayWrong();
    }

    // Any visible part counts: an object's center can be hidden, like books behind a shelf board.
    bool InPhoto(Anomaly anomaly)
    {
        var parts = new List<Bounds>();
        anomaly.CollectParts(parts);
        foreach (Bounds part in parts)
        {
            if (PartInPhoto(anomaly, part))
                return true;
        }
        return false;
    }

    bool PartInPhoto(Anomaly anomaly, Bounds bounds)
    {
        Vector3 c = bounds.center;
        Vector3 e = bounds.extents * 0.5f;
        Vector3[] points =
        {
            c,
            c + new Vector3(e.x, 0f, 0f), c - new Vector3(e.x, 0f, 0f),
            c + new Vector3(0f, e.y, 0f), c - new Vector3(0f, e.y, 0f),
            c + new Vector3(0f, 0f, e.z), c - new Vector3(0f, 0f, e.z),
        };

        Vector3 eye = view.transform.position;
        foreach (Vector3 point in points)
        {
            Vector3 viewport = view.WorldToViewportPoint(point);
            if (viewport.z <= 0f || viewport.z > photoRange || !photoFrame.Contains(viewport))
                continue;
            Vector3 toPoint = point - eye;
            bool blocked = Physics.Raycast(eye, toPoint.normalized, out RaycastHit hit, toPoint.magnitude, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
                && !anomaly.Owns(hit.collider);
            if (!blocked)
                return true;
        }
        return false;
    }

    // The room corrects itself inside the flash.
    IEnumerator Flash(List<Anomaly> photographed)
    {
        fade.color = Color.white;
        foreach (Anomaly anomaly in photographed)
            anomaly.Clear();
        yield return new WaitForSeconds(0.08f);
        if (CurrentPhase != Phase.Transition)
            fade.color = Color.clear;
    }

    IEnumerator RunNight()
    {
        yield return FadeOut();
        HideMoney();

        // Missed anomalies grow while you sleep; one with nowhere left to grow ends the run.
        bool lost = false;
        foreach (Anomaly anomaly in anomalies)
        {
            if (anomaly.Active && !anomaly.Develop())
                lost = true;
        }
        if (lost)
        {
            yield return Lost();
            yield break;
        }
        SpawnAnomalies();
        Film = filmPerNight + ExtraFilm;
        ExtraFilm = 0;

        player.Teleport(wakePoint.position, wakePoint.eulerAngles.y, wakePitch);
        look.FogNear = nightFogNear;
        look.FogFar = nightFogFar;
        SetLamp(nightLampIntensity, nightBrightness);
        SetDaylight(0f);
        notes.Hide();
        ShowCard("ночь " + Night, "", Color.white);
        yield return new WaitForSeconds(nightCardShownFor);
        HideMoney();
        yield return FadeIn();

        CurrentPhase = Phase.Night;
        sleepRequested = false;
        float time = 0f;
        while (time < nightLength && !sleepRequested)
        {
            time += Time.deltaTime;
            nightBar.localScale = new Vector3(time / nightLength, 1f, 1f);
            yield return null;
        }

        yield return FadeOut();
        Night++;
        BackToDay();
        yield return FadeIn();
        CurrentPhase = Phase.Day;
        ShowMoneyBriefly(Color.white);
    }

    void SpawnAnomalies()
    {
        var calm = new List<Anomaly>();
        foreach (Anomaly anomaly in anomalies)
        {
            if (!anomaly.Active && anomaly.FirstNight <= Night)
                calm.Add(anomaly);
        }

        int count = Night >= secondAnomalyFromNight && Random.value < secondAnomalyChance ? 2 : 1;
        for (int i = 0; i < count && calm.Count > 0; i++)
        {
            int pick = Random.Range(0, calm.Count);
            calm[pick].Begin();
            calm.RemoveAt(pick);
        }
    }

    IEnumerator Lost()
    {
        yield return Face();
        yield return new WaitForSeconds(1.2f);
        ShowNights(Color.white);
        yield return new WaitForSeconds(3f);
        yield return Restart();
    }

    // The fade is already black. It is not empty.
    IEnumerator Face()
    {
        yield return new WaitForSeconds(0.7f);
        lostFace.SetActive(true);
        sound.PlayStinger();
        yield return new WaitForSeconds(0.45f);
        lostFace.SetActive(false);
    }

    IEnumerator Restart()
    {
        HideMoney();
        ResetRun();
        ShowTitle();
        yield return FadeIn();
        player.Frozen = true;
        CurrentPhase = Phase.Day;
    }

    IEnumerator Leave()
    {
        if (Night > lastNightDoorOpens)
            yield return Trapped();
        else if (Money < goal)
            yield return LeftTooEarly();
        else
            yield return LeftInTime();
    }

    // You go, and you still owe.
    IEnumerator LeftTooEarly()
    {
        yield return FadeOut();
        HideMoney();
        sound.PlayDoor();
        ShowMoney(Color.white);
        ShowNights(goalColor);
        yield return new WaitForSeconds(5f);
        yield return Restart();
    }

    // Morning outside. Whatever you never photographed comes along.
    IEnumerator LeftInTime()
    {
        bool followed = false;
        foreach (Anomaly anomaly in anomalies)
            followed |= anomaly.Active;

        CurrentPhase = Phase.Transition;
        player.Frozen = true;
        HideMoney();
        sound.PlayDoor();
        sound.PlayOutside();
        yield return FadeTo(daylight, 2f);
        ShowCard("$" + Money, "ты ушёл", daylightText);
        ShowNights(daylightText);
        yield return new WaitForSeconds(5f);
        HideMoney();

        if (followed)
        {
            yield return new WaitForSeconds(1f);
            lostFace.SetActive(true);
            sound.StopCamera();
            sound.PlayStingerLong();
            yield return new WaitForSeconds(0.45f);
            lostFace.SetActive(false);
            fade.color = Color.black;
            yield return new WaitForSeconds(1.2f);
            ShowCard("", "не один", Color.white);
            yield return new WaitForSeconds(3f);
        }
        else
        {
            yield return FadeTo(Color.black, 1.5f);
            sound.StopCamera();
            yield return new WaitForSeconds(0.5f);
        }
        yield return Restart();
    }

    // Stayed too long: the door opens onto the same room, and all of it is wrong now.
    IEnumerator Trapped()
    {
        yield return FadeOut();
        HideMoney();
        sound.PlayDoor();
        yield return new WaitForSeconds(1.5f);

        foreach (Anomaly anomaly in anomalies)
        {
            if (!anomaly.Active)
                anomaly.Begin();
        }
        Film = filmPerNight;
        look.FogNear = nightFogNear;
        look.FogFar = nightFogFar;
        SetLamp(nightLampIntensity, nightBrightness);
        SetDaylight(0f);
        notes.Hide();
        nightBar.localScale = Vector3.one;
        player.Teleport(wakePoint.position, wakePoint.eulerAngles.y, wakePitch);
        yield return FadeIn();

        CurrentPhase = Phase.Night;
        trapped = true;
        sleepRequested = false;
        doorRequested = false;
        for (float time = 0f; time < trappedLength && !sleepRequested; time += Time.deltaTime)
        {
            if (doorRequested)
            {
                doorRequested = false;
                yield return FadeOut();
                sound.PlayDoor();
                yield return new WaitForSeconds(1.2f);
                player.Teleport(wakePoint.position, wakePoint.eulerAngles.y, wakePitch);
                yield return FadeIn();
                CurrentPhase = Phase.Night;
            }
            yield return null;
        }
        trapped = false;

        yield return FadeOut();
        yield return Face();
        yield return new WaitForSeconds(1.2f);
        ShowCard("", "ещё одну ночь", Color.white);
        ShowNights(Color.white);
        yield return new WaitForSeconds(4f);
        yield return Restart();
    }

    void ResetRun()
    {
        Money = 0;
        Night = 1;
        Film = filmPerNight;
        foreach (Anomaly anomaly in anomalies)
            anomaly.Clear();
        photoPrint.Clear();
        if (peephole != null)
            peephole.Clear();
        if (desk != null)
            desk.Clear();
        if (phone != null)
            phone.Clear();
        ExtraFilm = 0;
        notes.Clear();
        safeLock.Clear();
        foreach (DoorSwing swing in insideDoors)
            swing.Restore();
        BackToDay();
    }

    void BackToDay()
    {
        nightBar.localScale = new Vector3(0f, 1f, 1f);
        // Every morning is a little more like the night.
        float late = Lateness * dayDarkening;
        look.FogNear = Mathf.Lerp(dayFogNear, nightFogNear, late);
        look.FogFar = Mathf.Lerp(dayFogFar, nightFogFar, late);
        SetLamp(Mathf.Lerp(dayIntensity, nightLampIntensity, late), Mathf.Lerp(1f, nightBrightness, late));
        SetDaylight(1f - late);
        notes.ShowForToday();
        // The first day is for finding your way around; after that the day runs out.
        dayLight = 1f - late;
        dayLeft = dayLength;
        dayTimed = Night > 1;
        photoPrint.HauntOldPhotos(Night);
        NewTask();
        player.Teleport(wakePoint.position, wakePoint.eulerAngles.y, wakePitch);
    }

    void SetDaylight(float amount)
    {
        pane.SetColor(EmissionId, skyColor * amount);
        windowLight.intensity = windowLightIntensity * amount;
        windowLight.enabled = amount > 0f;
        for (int i = 0; i < moreWindowLights.Length; i++)
        {
            moreWindowLights[i].intensity = moreWindowLightIntensities[i] * amount;
            moreWindowLights[i].enabled = amount > 0f;
        }
        beam.SetFloat(IntensityId, amount);
        windowBeam.enabled = amount > 0f;
    }

    void FadeTheDay()
    {
        if (!dayTimed || CurrentPhase != Phase.Day)
            return;
        dayLeft -= Time.deltaTime;
        float left = Mathf.Clamp01(dayLeft / dayLength);
        nightBar.localScale = new Vector3(1f - left, 1f, 1f);
        SetDaylight(dayLight * Mathf.Lerp(dayEndsAt, 1f, left));
        if (dayLeft <= 0f && !safeLock.Busy && !notes.Reading)
        {
            dayTimed = false;
            StartCoroutine(RunNight());
        }
    }

    void SetLamp(float intensity, float newBrightness)
    {
        lamp.intensity = intensity;
        brightness = newBrightness;
    }

    /// <summary>The client's answer to a sent photo: paid for what is on it, fined for an empty frame.</summary>
    public void Settle(PhotoPrint.Shot shot)
    {
        int pay = (reportReward + reportRewardPerNight * (shot.Night - 1)) * shot.Found;
        // Decided when it was taken, since by the time it is sent the client wants another room.
        if (shot.ForTask)
            pay *= taskMultiplier;
        int change = shot.Found > 0 ? pay : -falseReportFine;
        if (shot.Ghost)
        {
            change += ghostReward;
            photoPrint.GhostComesCloser();
        }
        Money = Mathf.Max(0, Money + change);
        ShowMoneyBriefly(change >= 0 ? Color.white : fineColor);
        if (change >= 0)
            sound.PlayVanish();
        else
            sound.PlayWrong();
    }

    void ShowMoneyBriefly(Color color)
    {
        HideMoney();
        ShowMoney(color);
        moneyDisplay = StartCoroutine(HideMoneyAfterDelay());
    }

    IEnumerator HideMoneyAfterDelay()
    {
        yield return new WaitForSeconds(moneyShownFor);
        HideMoney();
    }

    void ShowMoney(Color color)
    {
        moneyText.text = "$" + Money;
        moneyText.color = color;
        goalText.text = "нужно $" + goal;
        goalText.color = goalColor;
        SetOutline(true);
        moneyText.gameObject.SetActive(true);
        goalText.gameObject.SetActive(Money < goal);
    }

    void ShowCard(string top, string line, Color color)
    {
        moneyText.text = top;
        moneyText.color = color;
        goalText.text = line;
        goalText.color = color;
        SetOutline(false);
        moneyText.gameObject.SetActive(true);
        goalText.gameObject.SetActive(true);
    }

    // How many nights this run lasted, for the ending cards.
    void ShowNights(Color color)
    {
        int nights = Night - 1;
        int tens = nights % 100;
        int ones = nights % 10;
        string word = tens >= 11 && tens <= 14 ? "ночей" : ones == 1 ? "ночь" : ones >= 2 && ones <= 4 ? "ночи" : "ночей";
        nightsText.text = nights + " " + word;
        nightsText.color = color;
        nightsText.gameObject.SetActive(true);
    }

    // The black outline keeps money readable over the room, but smears dark text on the daylight card.
    void SetOutline(bool on)
    {
        moneyText.GetComponent<Outline>().enabled = on;
        goalText.GetComponent<Outline>().enabled = on;
    }

    void HideMoney()
    {
        if (moneyDisplay != null)
            StopCoroutine(moneyDisplay);
        moneyDisplay = null;
        moneyText.gameObject.SetActive(false);
        goalText.gameObject.SetActive(false);
        nightsText.gameObject.SetActive(false);
    }

    IEnumerator FadeOut()
    {
        if (AtDesk)
            desk.Stand();
        if (Peeping)
            peephole.Close();
        CurrentPhase = Phase.Transition;
        player.Frozen = true;
        photoPrint.PutAway();
        yield return FadeTo(Color.black, 0.6f);
    }

    IEnumerator FadeIn()
    {
        yield return FadeTo(new Color(0f, 0f, 0f, 0f), 0.6f);
        player.Frozen = false;
    }

    IEnumerator FadeTo(Color target, float duration)
    {
        Color from = fade.color;
        for (float t = 0f; t < duration; t += Time.deltaTime)
        {
            fade.color = Color.Lerp(from, target, t / duration);
            yield return null;
        }
        fade.color = target;
    }
}
