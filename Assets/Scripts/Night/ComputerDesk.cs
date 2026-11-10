using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>
/// The kitchen computer. Sit down at it to go through every photo of this run, send them to the client,
/// compare a night photo with the day one, look closer, and open the last tenant's folder.
/// At night it sometimes turns on by itself with a photo nobody took.
/// </summary>
[RequireComponent(typeof(Collider))]
public class ComputerDesk : MonoBehaviour
{
    static readonly int BaseMapId = Shader.PropertyToID("_BaseMap");
    static readonly int BrightnessId = Shader.PropertyToID("_Brightness");

    [SerializeField] NightLoop loop;
    [SerializeField] FirstPersonController player;
    [SerializeField] Transform view;
    [SerializeField] PhotoPrint photos;
    [SerializeField] NoteCollection notes;
    [SerializeField] NightAudio sound;
    [SerializeField] Renderer screen;
    [SerializeField] Texture desktop;
    [SerializeField] Text caption;

    [Header("Sitting")]
    [SerializeField] Vector3 seat = new Vector3(-0.5f, 0f, 2.38f);
    [SerializeField] float seatYaw = 180f;
    [SerializeField] float seatPitch = 14f;
    [SerializeField] float eyeHeight = 1.12f;
    [SerializeField] float fieldOfView = 32f;

    [Header("Looking closer")]
    [SerializeField] float[] zoomSteps = { 1f, 2f, 4f };
    [SerializeField] float panSpeed = 0.0012f;
    [SerializeField] float blinkEvery = 0.45f;

    [Header("Her folder: where she stood to take them, what she looked at, and where the woman stands in it")]
    [SerializeField] Vector3[] herEyes =
    {
        new Vector3(-0.7f, 1.45f, -0.5f), new Vector3(-0.7f, 1.45f, -0.8f), new Vector3(2.9f, 2.0f, 3.0f),
        new Vector3(-2.1f, 1.45f, -1.8f), new Vector3(2.2f, 1.2f, -0.2f),
    };
    [SerializeField] Vector3[] herTargets =
    {
        new Vector3(-0.6f, 0.9f, 2.0f), new Vector3(-0.7f, 1.0f, -3.7f), new Vector3(2.0f, 0.5f, 0.0f),
        new Vector3(-3.25f, 1.3f, -1.8f), new Vector3(0.1f, 1.0f, -1.6f),
    };
    [Tooltip("Where the woman stands in each; a Y below 0 leaves her out.")]
    [SerializeField] Vector3[] herGhosts =
    {
        new Vector3(0f, -1f, 0f), new Vector3(-0.6f, 0f, -3.2f), new Vector3(1.0f, 0f, 0.3f),
        new Vector3(0f, -1f, 0f), new Vector3(0.6f, 0f, -1.4f),
    };
    [SerializeField] float[] herGhostYaws = { 0f, 0f, 70f, 0f, 60f };
    [Tooltip("The locked file: an empty stool at this computer, and her standing at it.")]
    [SerializeField] Vector3 lastEye = new Vector3(-0.5f, 1.55f, 3.25f);
    [SerializeField] Vector3 lastTarget = new Vector3(-0.5f, 0.9f, 1.8f);
    [SerializeField] Vector3 lastGhost = new Vector3(-0.5f, 0f, 2.6f);
    [SerializeField] float lastGhostYaw = 180f;

    [Header("At night")]
    [SerializeField] int turnsOnFromNight = 2;
    [SerializeField] float turnsOnChance = 0.5f;
    [SerializeField] Vector2 turnsOnAfter = new Vector2(15f, 45f);

    InputAction move;
    InputAction look;
    InputAction interact;
    InputAction aim;
    InputAction shutter;
    Material screenMaterial;
    Vector3 standPosition;
    float standYaw;
    float standPitch;
    float standEye;
    int satOnFrame;
    int stoodOnFrame = -1;

    bool hers;
    bool mail;
    int index;
    bool moveHeld;
    bool verticalHeld;
    PhotoPrint.Shot comparingWith;
    bool showingDay;
    float nextBlink;
    int zoomStep;
    Vector2 zoomCenter;
    readonly int[] typed = new int[NoteCollection.CodeLength];
    int typedCount;
    bool unlocked;
    [System.NonSerialized] RenderTexture[] herImages;
    RenderTexture lastImage;
    int nightChecked = -1;
    bool turnOnPending;
    float turnOnAt;

    public bool Seated { get; private set; }
    public float FieldOfView => fieldOfView;
    /// <summary>True on the frame the player got up, so the same E does not sit them down again.</summary>
    public bool JustStood => Time.frameCount == stoodOnFrame;

    int HerCount => herEyes.Length + 1;
    bool OnLockedFile => hers && index == HerCount - 1;

    void Awake()
    {
        move = InputSystem.actions.FindAction("Player/Move", true);
        look = InputSystem.actions.FindAction("Player/Look", true);
        interact = InputSystem.actions.FindAction("Player/Interact", true);
        aim = InputSystem.actions.FindAction("Player/Aim", true);
        shutter = InputSystem.actions.FindAction("Player/Attack", true);
        screenMaterial = screen.material;
        caption.gameObject.SetActive(false);
        ShowDesktop();
    }

    void OnDestroy()
    {
        if (herImages != null)
        {
            foreach (RenderTexture image in herImages)
                Free(image);
        }
        Free(lastImage);
    }

    static void Free(RenderTexture image)
    {
        if (image == null)
            return;
        image.Release();
        Destroy(image);
    }

    /// <summary>A new run: her file is locked again.</summary>
    public void Clear()
    {
        unlocked = false;
        typedCount = 0;
    }

    void Update()
    {
        // Its keys are read straight from the keyboard, which the pause does not switch off.
        if (PauseMenu.Paused)
            return;
        if (!Seated)
        {
            MaybeTurnOnAtNight();
            return;
        }
        if (Time.frameCount == satOnFrame)
            return;

        if (interact.WasPressedThisFrame() || aim.WasPressedThisFrame())
        {
            Stand();
            return;
        }
        Keyboard keys = Keyboard.current;
        if (keys != null && keys.fKey.wasPressedThisFrame)
        {
            // My photos, then the mail, then her folder.
            if (mail)
            {
                mail = false;
                hers = true;
            }
            else if (hers)
                hers = false;
            else
                mail = true;
            index = hers ? 0 : Mathf.Max(0, photos.Archive.Count - 1);
            ResetView();
            sound.PlayShutterEmpty();
            Show();
            return;
        }

        Vector2 input = move.ReadValue<Vector2>();
        if (Mathf.Abs(input.x) < 0.3f)
            moveHeld = false;
        else if (!moveHeld && Count > 0)
        {
            moveHeld = true;
            index = (index + (input.x > 0f ? 1 : Count - 1)) % Count;
            ResetView();
            sound.PlayShutterEmpty();
            Show();
        }

        if (Mathf.Abs(input.y) < 0.3f)
            verticalHeld = false;
        else if (!verticalHeld && mail)
        {
            verticalHeld = true;
            if (input.y > 0f)
                Order();
        }
        else if (!verticalHeld && !hers && Count > 0)
        {
            verticalHeld = true;
            if (input.y > 0f)
                Send(photos.Archive[index]);
            else
                ToggleCompare(photos.Archive[index]);
        }

        if (OnLockedFile && !unlocked)
            TypeDigits(keys);
        else if (shutter.WasPressedThisFrame() && Count > 0)
        {
            zoomStep = (zoomStep + 1) % zoomSteps.Length;
            zoomCenter = loop.PhotoFrame.center;
            sound.PlayShutterEmpty();
            Show();
        }

        if (zoomSteps[zoomStep] > 1f)
        {
            zoomCenter += look.ReadValue<Vector2>() * panSpeed / zoomSteps[zoomStep];
            ApplyFrame();
        }

        if (comparingWith != null && Time.time >= nextBlink)
        {
            nextBlink = Time.time + blinkEvery;
            showingDay = !showingDay;
            Show();
        }
    }

    int Count => mail ? 0 : hers ? HerCount : photos.Archive.Count;

    public void Sit()
    {
        Seated = true;
        satOnFrame = Time.frameCount;
        moveHeld = true;
        verticalHeld = true;
        standPosition = player.transform.position;
        standYaw = player.transform.eulerAngles.y;
        standPitch = Mathf.DeltaAngle(0f, view.localEulerAngles.x);
        standEye = view.localPosition.y;

        player.Frozen = true;
        player.Teleport(seat, seatYaw, seatPitch);
        SetEye(eyeHeight);
        hers = false;
        mail = false;
        index = Mathf.Max(0, photos.Archive.Count - 1);
        ResetView();
        caption.gameObject.SetActive(true);
        Show();
    }

    public void Stand()
    {
        Seated = false;
        stoodOnFrame = Time.frameCount;
        SetEye(standEye);
        player.Teleport(standPosition, standYaw, standPitch);
        player.Frozen = false;
        caption.gameObject.SetActive(false);
        ResetView();
        ShowDesktop();
    }

    void ResetView()
    {
        comparingWith = null;
        showingDay = false;
        zoomStep = 0;
        zoomCenter = loop.PhotoFrame.center;
        typedCount = 0;
    }

    void Send(PhotoPrint.Shot shot)
    {
        if (shot.Sent)
            return;
        if (loop.CurrentPhase != NightLoop.Phase.Day)
        {
            sound.PlayShutterEmpty();
            Show("ночью связи нет");
            return;
        }
        shot.Sent = true;
        loop.Settle(shot);
        Show();
    }

    void Order()
    {
        if (loop.CurrentPhase != NightLoop.Phase.Day)
        {
            sound.PlayShutterEmpty();
            Show("ночью связи нет");
            return;
        }
        if (!loop.OrderFilm())
        {
            sound.PlayWrong();
            Show("не хватает денег");
            return;
        }
        sound.PlayShutterEmpty();
        Show("заказ принят, привезут к ночи");
    }

    void ToggleCompare(PhotoPrint.Shot shot)
    {
        sound.PlayShutterEmpty();
        if (comparingWith != null)
        {
            comparingWith = null;
            showingDay = false;
            Show();
            return;
        }
        PhotoPrint.Shot day = shot.Day ? null : photos.DayPhotoLike(shot);
        if (day == null)
        {
            Show("нет дневного снимка этого места");
            return;
        }
        comparingWith = day;
        showingDay = false;
        nextBlink = Time.time + blinkEvery;
        Show();
    }

    void TypeDigits(Keyboard keys)
    {
        if (keys == null)
            return;
        for (int digit = 0; digit <= 9; digit++)
        {
            Key top = digit == 0 ? Key.Digit0 : Key.Digit1 + (digit - 1);
            Key pad = digit == 0 ? Key.Numpad0 : Key.Numpad1 + (digit - 1);
            if (!keys[top].wasPressedThisFrame && !keys[pad].wasPressedThisFrame)
                continue;
            typed[typedCount++] = digit;
            sound.PlayShutterEmpty();
            if (typedCount == typed.Length)
            {
                if (notes.CodeMatches(typed))
                {
                    unlocked = true;
                    sound.PlayVanish();
                }
                else
                {
                    sound.PlayWrong();
                }
                typedCount = 0;
            }
            Show();
            return;
        }
    }

    void MaybeTurnOnAtNight()
    {
        if (loop.CurrentPhase != NightLoop.Phase.Night)
            return;
        if (nightChecked != loop.Night)
        {
            nightChecked = loop.Night;
            turnOnPending = loop.Night >= turnsOnFromNight && Random.value < turnsOnChance;
            turnOnAt = Time.time + Random.Range(turnsOnAfter.x, turnsOnAfter.y);
        }
        if (!turnOnPending || Time.time < turnOnAt)
            return;
        turnOnPending = false;

        // From just behind the player, looking where they look. She stands where they stand.
        Vector3 forward = player.transform.forward;
        Vector3 head = player.transform.position + Vector3.up * 1.6f;
        float back = 1.1f;
        if (Physics.Raycast(head, -forward, out RaycastHit wall, back + 0.2f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            back = Mathf.Max(0.3f, wall.distance - 0.2f);
        Vector3 eye = head - forward * back;
        PhotoPrint.Shot shot = photos.TakeForeign(eye, Quaternion.LookRotation(player.transform.position + Vector3.up * 1.1f + forward * 1.5f - eye),
            player.transform.position, Quaternion.LookRotation(forward));
        ShowImage(shot.Image, true);
        sound.PlayShutterAt(screen.transform.position);
    }

    void SetEye(float height)
    {
        Vector3 local = view.localPosition;
        local.y = height;
        view.localPosition = local;
    }

    void ShowDesktop()
    {
        screenMaterial.SetFloat(BrightnessId, 0.95f);
        screenMaterial.SetTexture(BaseMapId, desktop);
        screenMaterial.SetTextureScale(BaseMapId, Vector2.one);
        screenMaterial.SetTextureOffset(BaseMapId, Vector2.zero);
    }

    void ShowImage(Texture image, bool photo)
    {
        screenMaterial.SetFloat(BrightnessId, 0.95f);
        screenMaterial.SetTexture(BaseMapId, image);
        if (photo)
            ApplyFrame();
        else
        {
            screenMaterial.SetTextureScale(BaseMapId, Vector2.one);
            screenMaterial.SetTextureOffset(BaseMapId, Vector2.zero);
        }
    }

    // The same part of the frame the print shows, or a smaller piece of it when looking closer.
    void ApplyFrame()
    {
        Rect frame = loop.PhotoFrame;
        float zoom = zoomSteps[zoomStep];
        Vector2 size = frame.size / zoom;
        zoomCenter.x = Mathf.Clamp(zoomCenter.x, frame.xMin + size.x / 2f, frame.xMax - size.x / 2f);
        zoomCenter.y = Mathf.Clamp(zoomCenter.y, frame.yMin + size.y / 2f, frame.yMax - size.y / 2f);
        screenMaterial.SetTextureScale(BaseMapId, size);
        screenMaterial.SetTextureOffset(BaseMapId, zoomCenter - size / 2f);
    }

    void Show(string note = null)
    {
        if (mail)
        {
            ShowDesktop();
            caption.text = "почта: " + (note ?? loop.TaskText) +
                           "\nW купить " + loop.FilmPack + " кадра за $" + loop.FilmPrice + (loop.ExtraFilm > 0 ? ", заказано " + loop.ExtraFilm : "") +
                           "\nF её папка   E встать";
            return;
        }
        if (hers)
        {
            ShowHers(note);
            return;
        }

        var archive = photos.Archive;
        if (archive.Count == 0)
        {
            ShowDesktop();
            caption.text = "снимков пока нет\nF почта   E встать";
            return;
        }

        PhotoPrint.Shot shot = archive[index];
        bool day = comparingWith != null && showingDay;
        ShowImage(day ? comparingWith.Image : shot.Image, true);
        // Whether it caught anything is for the player to judge: the screen only says if it went.
        string state = note ?? (comparingWith != null ? (day ? "днём" : "ночью") : shot.Sent ? "отправлен" : "не отправлен");
        string zoom = zoomSteps[zoomStep] > 1f ? ", ближе в " + zoomSteps[zoomStep] + " раза" : "";
        caption.text = "снимок " + (index + 1) + " из " + archive.Count + ", ночь " + shot.Night + ", " + state + zoom +
                       (shot.Sent ? "\nA/D листать   S сравнить" : "\nA/D листать   W отправить   S сравнить") +
                       "\nЛКМ ближе   F почта   E встать";
    }

    void ShowHers(string note)
    {
        if (herImages == null || herImages.Length != herEyes.Length)
        {
            herImages = new RenderTexture[herEyes.Length];
            for (int i = 0; i < herEyes.Length; i++)
                herImages[i] = photos.Stage(herEyes[i], herTargets[i], herGhosts[i].y >= 0f, herGhosts[i], herGhostYaws[i]);
        }

        string zoom = zoomSteps[zoomStep] > 1f ? ", ближе в " + zoomSteps[zoomStep] + " раза" : "";
        if (!OnLockedFile)
        {
            ShowImage(herImages[index], true);
            caption.text = "её папка, снимок " + (index + 1) + " из " + herEyes.Length + zoom + "\nA/D листать   ЛКМ ближе\nF мои снимки   E встать";
            return;
        }

        if (!unlocked)
        {
            ShowDesktop();
            screenMaterial.SetFloat(BrightnessId, 0.25f);
            var code = new System.Text.StringBuilder();
            for (int i = 0; i < typed.Length; i++)
                code.Append(i < typedCount ? typed[i].ToString() : "_").Append(i < typed.Length - 1 ? " " : "");
            caption.text = "её папка, файл заперт, пароль: " + code + (note != null ? ", " + note : "") + "\nцифры 0-9 ввести   A/D листать\nF мои снимки   E встать";
            return;
        }

        if (lastImage == null)
            lastImage = photos.Stage(lastEye, lastTarget, true, lastGhost, lastGhostYaw);
        ShowImage(lastImage, true);
        caption.text = "её папка, последний снимок" + zoom + "\nA/D листать   ЛКМ ближе\nF мои снимки   E встать";
    }
}
