using UnityEngine;

/// <summary>The TV hisses while its anomaly is active: louder at every stage, and lower and slower at the last one.</summary>
[RequireComponent(typeof(AudioSource))]
public class TvStatic : MonoBehaviour
{
    [SerializeField] Anomaly tv;
    [Tooltip("Volume at each stage, from the first.")]
    [SerializeField] float[] stageVolumes = { 0.25f, 0.45f, 0.7f };
    [SerializeField] float[] stagePitches = { 1f, 0.95f, 0.8f };
    [SerializeField] float fadePerSecond = 1.5f;

    AudioSource source;

    void Awake()
    {
        source = GetComponent<AudioSource>();
        source.loop = true;
        source.volume = 0f;
    }

    void Update()
    {
        int stage = tv.Stage;
        float target = stage > 0 ? stageVolumes[Mathf.Min(stage, stageVolumes.Length) - 1] : 0f;
        if (stage > 0)
        {
            source.pitch = stagePitches[Mathf.Min(stage, stagePitches.Length) - 1];
            if (!source.isPlaying)
                source.Play();
        }
        source.volume = Mathf.MoveTowards(source.volume, target, fadePerSecond * Time.deltaTime);
        if (stage == 0 && source.volume <= 0f && source.isPlaying)
            source.Stop();
    }
}
