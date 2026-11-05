using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>The print that comes out of the camera. It keeps what the room looked like, and sometimes something the room did not show you.</summary>
public class PhotoPrint : MonoBehaviour
{
    [Header("Scene")]
    [SerializeField] NightLoop loop;
    [SerializeField] Camera view;
    [Tooltip("Lights the room only for the photo itself.")]
    [SerializeField] Light flash;
    [Tooltip("Stands in the room only for the photo itself.")]
    [SerializeField] Renderer ghost;

    [Header("Print")]
    [SerializeField] RectTransform paper;
    [SerializeField] RawImage picture;
    [SerializeField] Vector2 restPosition = new Vector2(128f, 84f);
    [SerializeField] Vector2 hiddenPosition = new Vector2(128f, -90f);
    [SerializeField] Vector2 lookPosition = new Vector2(320f, 180f);
    [SerializeField] float lookScale = 2f;
    [SerializeField] float slideSpeed = 900f;
    [SerializeField] float shownFor = 5f;
    [SerializeField] float developTime = 2f;
    [SerializeField] Color undeveloped = new Color(0.12f, 0.12f, 0.12f);

    [Header("Ghost")]
    [SerializeField] float ghostChancePerNight = 0.08f;
    [SerializeField] float ghostChanceMax = 0.5f;
    [SerializeField] float ghostFirstDistance = 4f;
    [Tooltip("Each time it is caught on film, it is this much closer.")]
    [SerializeField] float ghostCloserEachTime = 0.7f;
    [SerializeField] float ghostNearest = 0.8f;

    RenderTexture photo;
    InputAction lookAtPhoto;
    bool hasPhoto;
    float takenAt;
    float shownUntil;
    int ghostsCaught;

    void Awake()
    {
        lookAtPhoto = InputSystem.actions.FindAction("Player/ViewPhoto", true);
        // A quarter of the output frame, so the cropped picture maps 1:1 onto low-res pixels.
        photo = new RenderTexture(320, 180, GraphicsFormat.R8G8B8A8_SRGB, GraphicsFormat.D24_UNorm_S8_UInt) { filterMode = FilterMode.Point };
        picture.texture = photo;
        picture.uvRect = loop.PhotoFrame;
        flash.enabled = false;
        ghost.enabled = false;
        paper.anchoredPosition = hiddenPosition;
    }

    void OnDestroy()
    {
        photo.Release();
        Destroy(photo);
    }

    void Update()
    {
        bool looking = hasPhoto && lookAtPhoto.IsPressed() && loop.CurrentPhase != NightLoop.Phase.Transition;
        bool showing = hasPhoto && Time.time < shownUntil;
        Vector2 target = looking ? lookPosition : showing ? restPosition : hiddenPosition;
        paper.anchoredPosition = Vector2.MoveTowards(paper.anchoredPosition, target, slideSpeed * Time.deltaTime);
        float scale = Mathf.MoveTowards(paper.localScale.x, looking ? lookScale : 1f, slideSpeed / 150f * Time.deltaTime);
        paper.localScale = new Vector3(scale, scale, 1f);
        picture.color = Color.Lerp(undeveloped, Color.white, (Time.time - takenAt) / developTime);
    }

    /// <summary>Call before the flash clears anything: the print keeps what was there.</summary>
    public void Capture()
    {
        bool caught = Random.value < Mathf.Min(ghostChanceMax, ghostChancePerNight * (loop.Night - 1)) && PlaceGhost();
        if (caught)
            ghostsCaught++;

        RenderTexture screen = view.targetTexture;
        int everything = view.cullingMask;
        flash.enabled = true;
        ghost.enabled = caught;
        view.targetTexture = photo;
        view.cullingMask = everything & ~(1 << LayerMask.NameToLayer("UI"));
        view.Render();
        view.cullingMask = everything;
        view.targetTexture = screen;
        flash.enabled = false;
        ghost.enabled = false;

        hasPhoto = true;
        takenAt = Time.time;
        shownUntil = Time.time + shownFor;
    }

    /// <summary>Between day and night. The last print can still be looked at.</summary>
    public void PutAway() => shownUntil = 0f;

    /// <summary>A new run: no print, and it starts from far away again.</summary>
    public void Clear()
    {
        hasPhoto = false;
        ghostsCaught = 0;
        paper.anchoredPosition = hiddenPosition;
        paper.localScale = Vector3.one;
    }

    // Stands it on the floor inside the frame, facing the lens. False if the shot has no room for it.
    bool PlaceGhost()
    {
        Rect frame = loop.PhotoFrame;
        Vector3 aim = view.ViewportPointToRay(new Vector3(Random.Range(frame.xMin + 0.1f, frame.xMax - 0.1f), 0.5f, 0f)).direction;
        aim.y = 0f;
        if (aim.sqrMagnitude < 0.01f)
            return false;
        aim.Normalize();

        const float WallGap = 0.4f;
        Vector3 eye = view.transform.position;
        float distance = Mathf.Max(ghostNearest, ghostFirstDistance - ghostCloserEachTime * ghostsCaught);
        if (Physics.Raycast(eye, aim, out RaycastHit wall, distance + WallGap, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            distance = wall.distance - WallGap;
        if (distance < ghostNearest)
            return false;

        Vector3 feet = eye + aim * distance;
        feet.y = view.transform.parent.position.y;
        ghost.transform.SetPositionAndRotation(feet, Quaternion.LookRotation(-aim));
        return InFrame(feet + Vector3.up * 1.5f, frame) || InFrame(feet + Vector3.up * 0.9f, frame);
    }

    bool InFrame(Vector3 point, Rect frame)
    {
        Vector3 viewport = view.WorldToViewportPoint(point);
        return viewport.z > 0f && frame.Contains(viewport);
    }
}
