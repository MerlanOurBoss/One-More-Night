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

    Renderer body;
    Collider solid;
    Vector3 homePosition;
    Quaternion homeRotation;
    Vector3 homeScale;
    Vector3 pivot;
    bool aiming;

    public override int StageCount => stages.Length;

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
        Pose pose = stage == 0 ? new Pose { scale = Vector3.one } : stages[stage - 1];
        Quaternion turn = Quaternion.Euler(pose.rotation);
        transform.localScale = Vector3.Scale(homeScale, pose.scale);
        transform.rotation = turn * homeRotation;
        transform.position = pivot + pose.offset + turn * Vector3.Scale(pose.scale, homePosition - pivot);

        for (int i = 0; i < stageExtras.Length; i++)
            stageExtras[i].SetActive(stage >= extrasFromStage + i);
        UpdateVisibility();
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
    }
}
