using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>Moves, turns or stretches an object around its visual center. Room meshes have their origin at the room center.</summary>
public class TransformAnomaly : Anomaly
{
    [Serializable]
    public struct Pose
    {
        public Vector3 offset;
        public Vector3 rotation;
        public Vector3 scale;
    }

    [SerializeField] Pose[] stages;

    [Tooltip("Turn around this point instead of the visual center, like a door on its hinge.")]
    [SerializeField] Transform pivotPoint;
    [Tooltip("Not in the room at all until the anomaly starts.")]
    [SerializeField] bool hiddenWhenCalm;
    [Tooltip("Can only be seen through the camera.")]
    [SerializeField] bool onlyThroughLens;
    [Tooltip("Extra objects: the first appears at Extras From Stage, the next one stage later, and so on.")]
    [SerializeField] GameObject[] stageExtras;
    [SerializeField] int extrasFromStage = 1;
    [Tooltip("Extras that can only be seen through the camera, like a face in the dark of an open fridge.")]
    [SerializeField] Renderer[] lensOnlyExtras = new Renderer[0];
    [Tooltip("A new stage does not show at once: it keeps its old pose until Reveal is called, and then swings there. ApplianceLife calls it when nobody is looking.")]
    [SerializeField] bool sneaks;
    [SerializeField] float swingSeconds = 2f;

    [Header("By hand")]
    [Tooltip("The player can open it, as far as its last stage. Shut again, it only goes back to what its stage holds it at: an open anomaly's door will not close.")]
    [SerializeField] bool opensByHand;
    [SerializeField] float handSeconds = 0.5f;
    [SerializeField] AudioClip openClip;
    [SerializeField] AudioClip closeClip;
    [Tooltip("Of the stage extras, those already there at any stage if you open it yourself.")]
    [SerializeField] GameObject[] handExtras = new GameObject[0];

    int shownStage;
    int pendingStage;
    bool handOpen;
    bool swinging;
    float swingLength;
    float swingTime;
    Vector3 swingFromPosition;
    Quaternion swingFromRotation;
    Vector3 swingToPosition;
    Quaternion swingToRotation;
    Renderer body;
    Collider solid;
    Vector3 homePosition;
    Quaternion homeRotation;
    Vector3 homeScale;
    Vector3 pivot;
    bool aiming;

    public override int StageCount => stages.Length;
    /// <summary>A door still waiting to move looks like any other shut door.</summary>
    public override bool Showing => shownStage > 0;

    public bool Sneaks => sneaks;
    public bool Pending => pendingStage > 0;
    /// <summary>At its last stage it stands as wide as it goes, and there is nothing left to do with it.</summary>
    public bool OpensByHand => opensByHand && shownStage < stages.Length;
    public bool OpenedByHand => handOpen;
    /// <summary>A door the player can open at all, whatever its stage.</summary>
    public bool HandDoor => opensByHand;

    void Awake()
    {
        body = GetComponent<Renderer>();
        Collider own = GetComponent<Collider>();
        solid = own.enabled ? own : null;
        homePosition = transform.position;
        homeRotation = transform.rotation;
        homeScale = transform.localScale;
        pivot = pivotPoint != null ? pivotPoint.position : Center;
        Apply(0);
    }

    public override void SetAiming(bool isAiming)
    {
        aiming = isAiming;
        UpdateVisibility();
    }

    protected override void Apply(int stage)
    {
        if (sneaks && stage > shownStage)
        {
            pendingStage = stage;
            return;
        }

        pendingStage = 0;
        swinging = false;
        shownStage = stage;
        if (stage == 0)
            handOpen = false;
        Pose pose = ShownPose();
        transform.localScale = Vector3.Scale(homeScale, pose.scale);
        transform.SetPositionAndRotation(PositionAt(pose), RotationAt(pose));
        ShowExtras(stage);
        UpdateVisibility();
    }

    /// <summary>Starts the swing to the stage it has been holding back. Scale stays: this is for things that turn.</summary>
    public void Reveal()
    {
        if (!Pending)
            return;
        shownStage = pendingStage;
        pendingStage = 0;
        ShowExtras(shownStage);
        SwingToShownPose(swingSeconds);
    }

    /// <summary>The player opens or shuts it. A stage that was waiting for them to look away has been caught at it.</summary>
    public void ToggleByHand()
    {
        handOpen = !handOpen;
        if (Pending)
        {
            shownStage = pendingStage;
            pendingStage = 0;
        }
        ShowExtras(shownStage);
        SwingToShownPose(handSeconds);
        AudioClip clip = handOpen ? openClip : closeClip;
        if (clip != null)
            AudioSource.PlayClipAtPoint(clip, Center);
    }

    /// <summary>Shut by nobody, while nobody looked: no sound, no hurry. Back to what its stage holds it at.</summary>
    public void ShutQuietly(float seconds)
    {
        if (!handOpen)
            return;
        handOpen = false;
        ShowExtras(shownStage);
        SwingToShownPose(seconds);
    }

    void SwingToShownPose(float seconds)
    {
        Pose pose = ShownPose();
        swingFromPosition = transform.position;
        swingFromRotation = transform.rotation;
        swingToPosition = PositionAt(pose);
        swingToRotation = RotationAt(pose);
        swingLength = seconds;
        swingTime = 0f;
        swinging = true;
    }

    void Update()
    {
        if (!swinging)
            return;
        swingTime += Time.deltaTime;
        float t = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(swingTime / swingLength));
        transform.SetPositionAndRotation(Vector3.Lerp(swingFromPosition, swingToPosition, t), Quaternion.Slerp(swingFromRotation, swingToRotation, t));
        if (swingTime >= swingLength)
            swinging = false;
    }

    Pose ShownPose() => handOpen ? stages[stages.Length - 1] : PoseAt(shownStage);

    Pose PoseAt(int stage) => stage == 0 ? new Pose { scale = Vector3.one } : stages[stage - 1];

    Quaternion RotationAt(Pose pose) => Quaternion.Euler(pose.rotation) * homeRotation;

    Vector3 PositionAt(Pose pose) => pivot + pose.offset + Quaternion.Euler(pose.rotation) * Vector3.Scale(pose.scale, homePosition - pivot);

    void ShowExtras(int stage)
    {
        bool byHand = handOpen && stage > 0;
        for (int i = 0; i < stageExtras.Length; i++)
            stageExtras[i].SetActive(stage >= extrasFromStage + i || (byHand && Array.IndexOf(handExtras, stageExtras[i]) >= 0));
    }

    public override void CollectParts(List<Bounds> parts)
    {
        base.CollectParts(parts);
        foreach (GameObject extra in stageExtras)
        {
            if (extra.activeSelf)
                parts.Add(extra.GetComponent<Renderer>().bounds);
        }
    }

    void UpdateVisibility()
    {
        bool present = Stage > 0 || !hiddenWhenCalm;
        body.enabled = present && (!onlyThroughLens || aiming);
        if (solid != null)
            solid.enabled = present;
        foreach (Renderer extra in lensOnlyExtras)
            extra.enabled = aiming;
    }
}
