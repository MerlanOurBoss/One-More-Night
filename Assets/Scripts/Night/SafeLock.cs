using System.Collections;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>The dead tenant's safe. The code is spread through her notes; inside is her last film, and you are on it.</summary>
public class SafeLock : MonoBehaviour
{
    [Header("Scene")]
    [SerializeField] NoteCollection notes;
    [SerializeField] FirstPersonController player;
    [SerializeField] NightAudio sound;
    [SerializeField] Collider safe;
    [Tooltip("The dark inside and the swung-out door.")]
    [SerializeField] GameObject openParts;
    [Tooltip("The shut door, hidden once it swings out.")]
    [SerializeField] GameObject closedParts;

    [Header("Lock screen")]
    [SerializeField] GameObject lockScreen;
    [SerializeField] Text wheelsText;
    [SerializeField] Text knownText;

    [Header("Film")]
    [SerializeField] GameObject filmScreen;
    [SerializeField] RawImage filmPrint;
    [SerializeField] Text filmCaption;
    [SerializeField] GameObject face;
    [SerializeField] Camera filmCamera;
    [Tooltip("Where her first frame can be taken from: the one farthest from the player is used.")]
    [SerializeField] Vector3[] filmCorners = { new Vector3(-2f, 2.05f, -1.55f), new Vector3(-2f, 2.05f, 1.55f), new Vector3(2f, 2.05f, -1.55f), new Vector3(2f, 2.05f, 1.55f) };
    [Tooltip("Stands where the player stands, only for these photos.")]
    [SerializeField] Renderer figure;

    readonly int[] wheels = new int[NoteCollection.CodeLength];
    InputAction move;
    InputAction interact;
    InputAction aim;
    RenderTexture photo;
    int cursor;
    int openedOnFrame;
    bool moveHeld;
    bool opened;
    bool inFilm;

    public bool Busy { get; private set; }

    public bool IsLocked(Collider target) => !opened && target == safe;

    void Awake()
    {
        move = InputSystem.actions.FindAction("Player/Move", true);
        interact = InputSystem.actions.FindAction("Player/Interact", true);
        aim = InputSystem.actions.FindAction("Player/Aim", true);
        photo = new RenderTexture(320, 180, GraphicsFormat.R8G8B8A8_SRGB, GraphicsFormat.D24_UNorm_S8_UInt) { filterMode = FilterMode.Point };
        filmCamera.targetTexture = photo;
        filmCamera.enabled = false;
        filmPrint.texture = photo;
        lockScreen.SetActive(false);
        filmScreen.SetActive(false);
        Clear();
    }

    void OnDestroy()
    {
        // On scene unload the camera may already be gone.
        if (filmCamera != null)
            filmCamera.targetTexture = null;
        photo.Release();
        Destroy(photo);
    }

    /// <summary>A new run: shut again.</summary>
    public void Clear()
    {
        opened = false;
        openParts.SetActive(false);
        closedParts.SetActive(true);
    }

    /// <summary>Walks away from the lock or the film at once: the run is being left.</summary>
    public void Close()
    {
        StopAllCoroutines();
        lockScreen.SetActive(false);
        filmScreen.SetActive(false);
        face.SetActive(false);
        figure.enabled = false;
        inFilm = false;
        Busy = false;
        player.Frozen = false;
    }

    public void Open()
    {
        Busy = true;
        player.Frozen = true;
        openedOnFrame = Time.frameCount;
        cursor = 0;
        moveHeld = true;
        System.Array.Clear(wheels, 0, wheels.Length);
        knownText.text = "код: " + notes.KnownCode();
        ShowWheels();
        lockScreen.SetActive(true);
    }

    void Update()
    {
        if (!Busy || inFilm || Time.frameCount == openedOnFrame)
            return;

        if (aim.WasPressedThisFrame())
        {
            lockScreen.SetActive(false);
            player.Frozen = false;
            Busy = false;
            return;
        }
        if (interact.WasPressedThisFrame())
        {
            if (notes.CodeMatches(wheels))
                StartCoroutine(ShowFilm());
            else
                sound.PlayWrong();
            return;
        }

        Vector2 input = move.ReadValue<Vector2>();
        if (input.magnitude < 0.3f)
            moveHeld = false;
        else if (!moveHeld)
        {
            moveHeld = true;
            if (Mathf.Abs(input.y) > Mathf.Abs(input.x))
                wheels[cursor] = (wheels[cursor] + (input.y > 0f ? 1 : 9)) % 10;
            else
                cursor = (cursor + (input.x > 0f ? 1 : wheels.Length - 1)) % wheels.Length;
            sound.PlayShutterEmpty();
            ShowWheels();
        }
    }

    void ShowWheels()
    {
        var text = new System.Text.StringBuilder();
        for (int i = 0; i < wheels.Length; i++)
            text.Append(i == cursor ? "[" + wheels[i] + "]" : " " + wheels[i] + " ");
        wheelsText.text = text.ToString();
    }

    IEnumerator ShowFilm()
    {
        inFilm = true;
        opened = true;
        lockScreen.SetActive(false);
        openParts.SetActive(true);
        closedParts.SetActive(false);
        sound.PlayCreakAt(safe.bounds.center);

        filmPrint.enabled = false;
        filmCaption.gameObject.SetActive(false);
        filmScreen.SetActive(true);
        yield return new WaitForSeconds(2f);

        // Her last three frames: you, from the far corner, then from right behind you.
        Vector3 feet = player.transform.position;
        Vector3 chest = feet + Vector3.up * 1.1f;
        Vector3 head = feet + Vector3.up * 1.5f;
        Vector3 back = -player.transform.forward;
        Photograph(FarCorner(feet), chest, feet);
        yield return HoldPrint();
        Photograph(BehindPlayer(head, back, 1.5f), chest, feet);
        yield return HoldPrint();
        Photograph(BehindPlayer(head, back, 0.55f), head, feet);
        yield return HoldPrint();

        filmPrint.enabled = false;
        yield return new WaitForSeconds(0.6f);
        face.SetActive(true);
        sound.PlayStinger();
        yield return new WaitForSeconds(0.45f);
        face.SetActive(false);
        yield return new WaitForSeconds(1.2f);
        filmCaption.gameObject.SetActive(true);
        yield return new WaitForSeconds(3.5f);

        filmScreen.SetActive(false);
        player.Frozen = false;
        inFilm = false;
        Busy = false;
    }

    IEnumerator HoldPrint()
    {
        filmPrint.enabled = true;
        sound.PlayShutter();
        // Until E, but never so fast that the shot goes unseen.
        yield return new WaitForSeconds(1f);
        for (float t = 0f; t < 5f && !interact.WasPressedThisFrame(); t += Time.deltaTime)
            yield return null;
    }

    void Photograph(Vector3 from, Vector3 lookAt, Vector3 feet)
    {
        filmCamera.transform.SetPositionAndRotation(from, Quaternion.LookRotation(lookAt - from));
        Vector3 facing = player.transform.forward;
        figure.transform.SetPositionAndRotation(feet, Quaternion.LookRotation(facing));
        figure.enabled = true;
        filmCamera.Render();
        figure.enabled = false;
    }

    Vector3 FarCorner(Vector3 feet)
    {
        Vector3 best = feet;
        foreach (Vector3 corner in filmCorners)
        {
            if (Vector3.Distance(corner, feet) > Vector3.Distance(best, feet))
                best = corner;
        }
        return best;
    }

    // Stops short of a wall behind the player.
    static Vector3 BehindPlayer(Vector3 head, Vector3 back, float distance)
    {
        if (Physics.Raycast(head, back, out RaycastHit wall, distance + 0.2f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            distance = Mathf.Max(0.2f, wall.distance - 0.2f);
        return head + back * distance;
    }
}
