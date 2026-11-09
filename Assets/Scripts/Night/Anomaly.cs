using System.Collections.Generic;
using UnityEngine;

/// <summary>Something in the room that can go wrong. Stage 0 is normal; a missed anomaly climbs towards StageCount.</summary>
[RequireComponent(typeof(Renderer), typeof(Collider))]
public abstract class Anomaly : MonoBehaviour
{
    [Tooltip("The first night this anomaly can appear. Quiet ones early, the worst ones later.")]
    [SerializeField] int firstNight = 1;

    public int FirstNight => firstNight;
    public int Stage { get; private set; }
    public bool Active => Stage > 0;
    /// <summary>Whether there is anything to see yet: only then can it be caught on film.</summary>
    public virtual bool Showing => Active;
    public Bounds Bounds => GetComponent<Renderer>().bounds;
    public Vector3 Center => Bounds.center;

    public abstract int StageCount { get; }

    public bool Owns(Collider target) => target == GetComponent<Collider>();

    public void Begin() => SetStage(1);
    public void Clear() => SetStage(0);

    /// <summary>Returns false when it has nowhere left to grow.</summary>
    public bool Develop()
    {
        if (Stage >= StageCount)
            return false;
        SetStage(Stage + 1);
        return true;
    }

    void SetStage(int stage)
    {
        Stage = stage;
        Apply(stage);
    }

    /// <summary>Everything that shows this anomaly: a photo of any of these parts counts.</summary>
    public virtual void CollectParts(List<Bounds> parts) => parts.Add(Bounds);

    /// <summary>Told every frame whether the player is looking through the camera.</summary>
    public virtual void SetAiming(bool aiming) { }

    protected abstract void Apply(int stage);
}
