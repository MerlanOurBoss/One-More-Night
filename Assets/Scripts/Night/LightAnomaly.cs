using System.Collections.Generic;
using UnityEngine;

/// <summary>The lamp slowly stops being the right color. Sits on the lamp's model so it can be reported.</summary>
public class LightAnomaly : Anomaly
{
    [SerializeField] Light target;
    [SerializeField] Color[] stages;
    [Tooltip("Lights spread around a home: a photo of any one of these counts.")]
    [SerializeField] Vector3[] spots = new Vector3[0];

    Color homeColor;

    public override int StageCount => stages.Length;

    void Awake()
    {
        homeColor = target.color;
    }

    public override void CollectParts(List<Bounds> parts)
    {
        base.CollectParts(parts);
        foreach (Vector3 spot in spots)
            parts.Add(new Bounds(spot, Vector3.one * 0.1f));
    }

    protected override void Apply(int stage)
    {
        target.color = stage == 0 ? homeColor : stages[stage - 1];
    }
}
