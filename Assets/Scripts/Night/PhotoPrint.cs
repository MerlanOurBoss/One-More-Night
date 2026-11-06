using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>The print that comes out of the camera. It keeps what the room looked like, and sometimes something the room did not show you.</summary>
public class PhotoPrint : MonoBehaviour
{
    /// <summary>One photo of this run, kept for the computer.</summary>
    public class Shot
    {
        public RenderTexture Image;
        public int Night;
        /// <summary>How many anomalies it caught. 0 is an empty frame.</summary>
        public int Found;
        public bool Ghost;
        public bool Sent;
        /// <summary>Taken by day: the one to compare a night photo with.</summary>
        public bool Day;
        /// <summary>Not taken by the player at all.</summary>
        public bool Foreign;
        /// <summary>How many times it has changed by itself.</summary>
        public int Haunted;
        public Vector3 Eye;
        public Quaternion Look;
        public float FieldOfView;
    }

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

    [Header("Old photos change")]
    [Tooltip("An empty photo this many nights old can start to show her.")]
    [SerializeField] int hauntAfterNights = 2;
    [SerializeField] float hauntChance = 0.6f;
    [SerializeField] float hauntFirstDistance = 3.2f;
    [SerializeField] float hauntCloserEachTime = 0.7f;
    [SerializeField] int hauntAtMost = 4;

    [Tooltip("The oldest photos are let go after this many.")]
    [SerializeField] int keepAtMost = 40;

    readonly List<Shot> archive = new List<Shot>();
    public IReadOnlyList<Shot> Archive => archive;

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
        ForgetAll();
    }

    void Update()
    {
        // At the computer the photos are on its screen, so the print keeps out of the way.
        bool looking = hasPhoto && lookAtPhoto.IsPressed() && loop.CurrentPhase != NightLoop.Phase.Transition && !loop.AtDesk;
        bool showing = hasPhoto && Time.time < shownUntil && !loop.AtDesk;
        Vector2 target = looking ? lookPosition : showing ? restPosition : hiddenPosition;
        paper.anchoredPosition = Vector2.MoveTowards(paper.anchoredPosition, target, slideSpeed * Time.deltaTime);
        float scale = Mathf.MoveTowards(paper.localScale.x, looking ? lookScale : 1f, slideSpeed / 150f * Time.deltaTime);
        paper.localScale = new Vector3(scale, scale, 1f);
        picture.color = Color.Lerp(undeveloped, Color.white, (Time.time - takenAt) / developTime);
    }

    /// <summary>Call before the flash clears anything: the print keeps what was there.</summary>
    public void Capture(int found)
    {
        float distance = Mathf.Max(ghostNearest, ghostFirstDistance - ghostCloserEachTime * ghostsCaught);
        bool caught = Random.value < Mathf.Min(ghostChanceMax, ghostChancePerNight * (loop.Night - 1)) && PlaceGhost(distance);
        if (caught)
            ghostsCaught++;
        Render(photo, caught);

        var copy = NewImage();
        Graphics.Blit(photo, copy);
        Keep(new Shot
        {
            Image = copy, Night = loop.Night, Found = found, Ghost = caught, Day = loop.CurrentPhase == NightLoop.Phase.Day,
            Eye = view.transform.position, Look = view.transform.rotation, FieldOfView = view.fieldOfView,
        });

        hasPhoto = true;
        takenAt = Time.time;
        shownUntil = Time.time + shownFor;
    }

    RenderTexture NewImage() => new RenderTexture(photo.width, photo.height, 24, photo.graphicsFormat) { filterMode = FilterMode.Point };

    void Keep(Shot shot)
    {
        archive.Add(shot);
        if (archive.Count > keepAtMost)
        {
            archive[0].Image.Release();
            Destroy(archive[0].Image);
            archive.RemoveAt(0);
        }
    }

    // The room as the camera sees it, lit by the flash, with or without her.
    void Render(RenderTexture target, bool withGhost)
    {
        RenderTexture screen = view.targetTexture;
        int everything = view.cullingMask;
        flash.enabled = true;
        ghost.enabled = withGhost;
        view.targetTexture = target;
        view.cullingMask = everything & ~(1 << LayerMask.NameToLayer("UI"));
        view.Render();
        view.cullingMask = everything;
        view.targetTexture = screen;
        flash.enabled = false;
        ghost.enabled = false;
    }

    // Puts the camera somewhere else for one render. The player never sees it move.
    void FromPose(Vector3 eye, Quaternion look, float fieldOfView, System.Action action)
    {
        Transform t = view.transform;
        Vector3 position = t.position;
        Quaternion rotation = t.rotation;
        float fov = view.fieldOfView;
        t.SetPositionAndRotation(eye, look);
        view.fieldOfView = fieldOfView;
        action();
        t.SetPositionAndRotation(position, rotation);
        view.fieldOfView = fov;
    }

    /// <summary>Each morning: an old empty photo may now show her, a little closer every time it changes.</summary>
    public void HauntOldPhotos(int night)
    {
        foreach (Shot shot in archive)
        {
            if (shot.Found > 0 || shot.Foreign || shot.Haunted >= hauntAtMost || night - shot.Night < hauntAfterNights || Random.value > hauntChance)
                continue;
            float distance = Mathf.Max(ghostNearest, hauntFirstDistance - hauntCloserEachTime * shot.Haunted);
            FromPose(shot.Eye, shot.Look, shot.FieldOfView, () =>
            {
                if (!PlaceGhost(distance))
                    return;
                Render(shot.Image, true);
                shot.Haunted++;
                shot.Ghost = true;
            });
        }
    }

    /// <summary>A photo from where nobody stood: her, standing where the player stands.</summary>
    public Shot TakeForeign(Vector3 eye, Quaternion look, Vector3 feet, Quaternion facing)
    {
        var image = NewImage();
        FromPose(eye, look, 60f, () =>
        {
            ghost.transform.SetPositionAndRotation(feet, facing);
            Render(image, true);
        });
        var shot = new Shot { Image = image, Night = loop.Night, Ghost = true, Foreign = true, Eye = eye, Look = look, FieldOfView = 60f };
        Keep(shot);
        return shot;
    }

    /// <summary>A photo set up by hand, kept by the caller: the last tenant's pictures.</summary>
    public RenderTexture Stage(Vector3 eye, Vector3 lookAt, bool withGhost, Vector3 feet, float ghostYaw)
    {
        var image = NewImage();
        bool fits = withGhost && NearestClear(ref feet);
        FromPose(eye, Quaternion.LookRotation(lookAt - eye), 60f, () =>
        {
            ghost.transform.SetPositionAndRotation(feet, Quaternion.Euler(0f, ghostYaw, 0f));
            Render(image, fits);
        });
        return image;
    }

    /// <summary>The day photo taken from about the same place, looking about the same way.</summary>
    public Shot DayPhotoLike(Shot night)
    {
        Shot best = null;
        float bestScore = float.MaxValue;
        foreach (Shot shot in archive)
        {
            if (!shot.Day || shot == night || shot.Foreign)
                continue;
            float apart = Vector3.Distance(shot.Eye, night.Eye);
            float angle = Quaternion.Angle(shot.Look, night.Look);
            if (apart > 0.9f || angle > 28f)
                continue;
            float score = apart + angle / 30f;
            if (score < bestScore)
            {
                bestScore = score;
                best = shot;
            }
        }
        return best;
    }

    /// <summary>Sending her picture away brings her a step closer on the next one.</summary>
    public void GhostComesCloser() => ghostsCaught++;

    /// <summary>Between day and night. The last print can still be looked at.</summary>
    public void PutAway() => shownUntil = 0f;

    /// <summary>A new run: no print, and it starts from far away again.</summary>
    public void Clear()
    {
        hasPhoto = false;
        ghostsCaught = 0;
        ForgetAll();
        paper.anchoredPosition = hiddenPosition;
        paper.localScale = Vector3.one;
    }

    void ForgetAll()
    {
        foreach (Shot shot in archive)
        {
            shot.Image.Release();
            Destroy(shot.Image);
        }
        archive.Clear();
    }

    // Stands it on the floor inside the frame, facing the lens. False if the shot has no room for it.
    // Tries a few spots across the frame, at and near the wanted distance. False if the shot has no room for her.
    bool PlaceGhost(float distance)
    {
        Rect frame = loop.PhotoFrame;
        Vector3 eye = view.transform.position;
        const float WallGap = 0.4f;
        for (int attempt = 0; attempt < 12; attempt++)
        {
            Vector3 aim = view.ViewportPointToRay(new Vector3(Random.Range(frame.xMin + 0.1f, frame.xMax - 0.1f), 0.5f, 0f)).direction;
            aim.y = 0f;
            if (aim.sqrMagnitude < 0.01f)
                continue;
            aim.Normalize();
            float reach = distance;
            if (Physics.Raycast(eye, aim, out RaycastHit wall, reach + WallGap, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                reach = wall.distance - WallGap;
            for (float d = reach; d >= ghostNearest; d -= 0.3f)
            {
                Vector3 feet = eye + aim * d;
                feet.y = 0f;
                if (!IsClear(feet) || !InFrame(feet + Vector3.up * 1.3f, frame))
                    continue;
                // Seen, not hidden behind something.
                if (Physics.Linecast(eye, feet + Vector3.up * 1.3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    continue;
                ghost.transform.SetPositionAndRotation(feet, Quaternion.LookRotation(-aim));
                return true;
            }
        }
        return false;
    }

    const float GhostRadius = 0.22f;

    /// <summary>Room for her to stand here: on the floor, and not in any furniture or wall.</summary>
    public static bool IsClear(Vector3 feet)
    {
        Vector3 low = feet + Vector3.up * (0.1f + GhostRadius);
        Vector3 high = feet + Vector3.up * (1.72f - GhostRadius);
        if (Physics.CheckCapsule(low, high, GhostRadius, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            return false;
        return Physics.Raycast(feet + Vector3.up * 0.5f, Vector3.down, out RaycastHit floor, 0.6f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
               && floor.point.y < 0.05f;
    }

    /// <summary>The nearest spot she fits, spiralling out from the one asked for.</summary>
    static bool NearestClear(ref Vector3 feet)
    {
        if (IsClear(feet))
            return true;
        for (float r = 0.1f; r <= 0.9f; r += 0.1f)
        {
            for (int k = 0; k < 16; k++)
            {
                float a = k * Mathf.PI / 8f;
                Vector3 spot = feet + new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a)) * r;
                if (IsClear(spot))
                {
                    feet = spot;
                    return true;
                }
            }
        }
        return false;
    }

    bool InFrame(Vector3 point, Rect frame)
    {
        Vector3 viewport = view.WorldToViewportPoint(point);
        return viewport.z > 0f && frame.Contains(viewport);
    }
}
