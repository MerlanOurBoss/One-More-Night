using UnityEngine;

/// <summary>Turns a head towards the player, as far as it can. The mesh's face looks along +X; the head turns around its origin, under the chin.</summary>
[RequireComponent(typeof(Renderer))]
public class HeadWatch : MonoBehaviour
{
    // A head stands inside things. Only what is more than this far in front of it can hide it from view.
    const float OwnSurroundings = 0.6f;

    static readonly Plane[] Frustum = new Plane[6];

    [Tooltip("The player's eye.")]
    [SerializeField] Camera view;
    [SerializeField] float degreesPerSecond = 20f;
    [Tooltip("How far it can turn sideways from how it stands in the scene.")]
    [SerializeField] float maxAngle = 60f;
    [Tooltip("How far it can tip up or down.")]
    [SerializeField] float maxPitch = 35f;
    [Tooltip("It only moves while you can't see it: every glance finds it further round. Otherwise it only moves while you can.")]
    [SerializeField] bool onlyUnseen;
    [Tooltip("Each time it comes into view through the lens it looks this far away from you, and has to find you again. 0: it stays where it got to.")]
    [SerializeField] float lookAway;

    Renderer body;
    Quaternion rest;
    bool wasShown;

    void Awake()
    {
        body = GetComponent<Renderer>();
        rest = transform.localRotation;
    }

    void OnEnable()
    {
        transform.localRotation = rest;
        wasShown = false;
    }

    void Update()
    {
        // Renderer off: the lens is down. It can change while no one can see it.
        if (body.enabled && !wasShown && lookAway > 0f)
        {
            float side = Random.value < 0.5f ? -1f : 1f;
            transform.localRotation = Quaternion.AngleAxis(side * Random.Range(0.5f, 1f) * lookAway, Vector3.up) * TowardsEye();
        }
        wasShown = body.enabled;

        if (Seen() != onlyUnseen)
            transform.localRotation = Quaternion.RotateTowards(transform.localRotation, TowardsEye(), degreesPerSecond * Time.deltaTime);
    }

    // Round and then up, like a neck: the shortest turn in space would roll the head over on its side.
    Quaternion TowardsEye()
    {
        Vector3 toEye = transform.parent.InverseTransformDirection(view.transform.position - transform.position).normalized;
        Vector3 face = rest * Vector3.right;
        float yaw = Vector3.SignedAngle(Vector3.ProjectOnPlane(face, Vector3.up), Vector3.ProjectOnPlane(toEye, Vector3.up), Vector3.up);
        Quaternion turn = Quaternion.AngleAxis(Mathf.Clamp(yaw, -maxAngle, maxAngle), Vector3.up);
        face = turn * face;
        float pitch = (Mathf.Asin(toEye.y) - Mathf.Asin(face.y)) * Mathf.Rad2Deg;
        return Quaternion.AngleAxis(Mathf.Clamp(pitch, -maxPitch, maxPitch), Vector3.Cross(face, Vector3.up)) * turn * rest;
    }

    /// <summary>No slow turn: it is looking at you, as far as its neck goes.</summary>
    public void LookAtEyeNow() => transform.localRotation = TowardsEye();

    public bool Seen()
    {
        if (!body.enabled)
            return false;
        GeometryUtility.CalculateFrustumPlanes(view, Frustum);
        if (!GeometryUtility.TestPlanesAABB(Frustum, body.bounds))
            return false;
        Vector3 eye = view.transform.position;
        Vector3 toHead = body.bounds.center - eye;
        return toHead.magnitude <= OwnSurroundings
            || !Physics.Linecast(eye, eye + toHead.normalized * (toHead.magnitude - OwnSurroundings), Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
    }
}
