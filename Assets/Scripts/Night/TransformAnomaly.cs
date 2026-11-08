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

    int shownStage;
    int pendingStage;
    bool swinging;
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

    public bool Sneaks => sneaks;
    public bool Pending => pendingStage > 0;

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
            swinging = false;
            return;
        }

        pendingStage = 0;
        swinging = false;
        shownStage = stage;
        Pose pose = PoseAt(stage);
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
        Pose pose = PoseAt(pendingStage);
        shownStage = pendingStage;
        pendingStage = 0;
        ShowExtras(shownStage);
        swingFromPosition = transform.position;
        swingFromRotation = transform.rotation;
        swingToPosition = PositionAt(pose);
        swingToRotation = RotationAt(pose);
        swingTime = 0f;
        swinging = true;
    }

    void Update()
    {
        if (!swinging)
            return;
        swingTime += Time.deltaTime;
        float t = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(swingTime / swingSeconds));
        transform.SetPositionAndRotation(Vector3.Lerp(swingFromPosition, swingToPosition, t), Quaternion.Slerp(swingFromRotation, swingToRotation, t));
        if (swingTime >= swingSeconds)
            swinging = false;
    }

    Pose PoseAt(int stage) => stage == 0 ? new Pose { scale = Vector3.one } : stages[stage - 1];

    Quaternion RotationAt(Pose pose) => Quaternion.Euler(pose.rotation) * homeRotation;

    Vector3 PositionAt(Pose pose) => pivot + pose.offset + Quaternion.Euler(pose.rotation) * Vector3.Scale(pose.scale, homePosition - pivot);

    void ShowExtras(int stage)
    {
        for (int i = 0; i < stageExtras.Length; i++)
            stageExtras[i].SetActive(stage >= extrasFromStage + i);
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
