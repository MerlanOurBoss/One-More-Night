using UnityEngine;

/// <summary>The picture on an object changes while nothing else moves.</summary>
public class TextureAnomaly : Anomaly
{
    static readonly int BaseMapId = Shader.PropertyToID("_BaseMap");

    [SerializeField] Texture[] stages;

    Material material;
    Texture homeTexture;

    public override int StageCount => stages.Length;

    void Awake()
    {
        material = GetComponent<Renderer>().material;
        homeTexture = material.GetTexture(BaseMapId);
    }

    protected override void Apply(int stage)
    {
        material.SetTexture(BaseMapId, stage == 0 ? homeTexture : stages[stage - 1]);
    }
}
