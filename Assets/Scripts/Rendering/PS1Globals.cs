using UnityEngine;

/// <summary>One place for the look of the whole scene. Raise Jitter from code near an anomaly.</summary>
[ExecuteAlways]
public class PS1Globals : MonoBehaviour
{
    [SerializeField] Vector2Int resolution = new Vector2Int(640, 360);

    [Tooltip("Vertex grid step in low-res pixels.")]
    [Min(0.01f)] public float Jitter = 2f;

    [Range(0f, 1f)] public float Affine = 0.25f;

    public Color Ambient = new Color(0.03f, 0.03f, 0.04f);
    [Tooltip("The most a light's falloff may give, so walls and ceilings next to a lamp don't burn out.")]
    public float LightCap = 1000f;
    public Color FogColor = Color.black;
    [Min(0f)] public float FogNear = 1.5f;
    [Min(0.01f)] public float FogFar = 8f;

    void OnEnable() => Apply();
    void OnValidate() => Apply();
    void Update() => Apply();

    void Apply()
    {
        // Clip space spans 2 units, so one low-res pixel is 2 / resolution.
        Shader.SetGlobalVector("_PS1SnapGrid", (Vector2)resolution / (2f * Jitter));
        Shader.SetGlobalFloat("_PS1Affine", Affine);
        Shader.SetGlobalVector("_PS1Fog", new Vector2(FogNear, Mathf.Max(FogFar, FogNear + 0.01f)));
        Shader.SetGlobalColor("_PS1FogColor", FogColor.linear);
        Shader.SetGlobalColor("_PS1Ambient", Ambient.linear);
        Shader.SetGlobalFloat("_PS1LightCap", LightCap);
    }
}
