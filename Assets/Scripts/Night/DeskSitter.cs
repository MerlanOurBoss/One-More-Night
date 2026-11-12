using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Someone at the kitchen computer. First she sits on its stool, head bowed to the screen.
/// Then she has looked up at you: her head turns your way whenever you look away.
/// Then the stool is empty and she stands between you and it. While she sits there the computer is hers.
/// </summary>
public class DeskSitter : Anomaly
{
    [Tooltip("Her head on the sitting body. Off at the first stage, so it stays bowed; on at the second, set to turn only while unseen.")]
    [SerializeField] HeadWatch sittingHead;
    [Tooltip("A child: her, standing, with a head of her own. No collider, since a photo only lets the sitting body's own collider through.")]
    [SerializeField] GameObject standing;
    [Tooltip("Where she stands at the last stage. The whole object goes there, so that the fog and the breathing find her.")]
    [SerializeField] Vector3 standAt = new Vector3(-0.55f, 0f, 0.75f);

    Renderer body;
    Collider solid;
    Renderer[] standingParts;
    Renderer headPart;
    Vector3 home;

    public override int StageCount => 3;
    /// <summary>On the computer's stool: nobody else can sit there.</summary>
    public bool AtDesk => Stage == 1 || Stage == 2;

    void Awake()
    {
        body = GetComponent<Renderer>();
        solid = GetComponent<Collider>();
        standingParts = standing.GetComponentsInChildren<Renderer>(true);
        headPart = sittingHead.GetComponent<Renderer>();
        home = transform.position;
        Apply(0);
    }

    protected override void Apply(int stage)
    {
        bool sitting = stage == 1 || stage == 2;
        transform.position = stage == 3 ? standAt : home;
        body.enabled = sitting;
        solid.enabled = sitting;
        sittingHead.gameObject.SetActive(sitting);
        sittingHead.enabled = stage == 2;
        standing.SetActive(stage == 3);
    }

    public override void CollectParts(List<Bounds> parts)
    {
        if (AtDesk)
        {
            parts.Add(Bounds);
            parts.Add(headPart.bounds);
        }
        else if (Stage == 3)
        {
            foreach (Renderer part in standingParts)
                parts.Add(part.bounds);
        }
    }
}
