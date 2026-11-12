using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

/// <summary>
/// The player's own photos, taped to a wall. First a few, as she took them. Then more, and the woman stands in every one, closer.
/// Then the last one goes up: the player asleep, taken from the ceiling.
/// </summary>
public class PhotoWall : Anomaly
{
    static readonly int BaseMapId = Shader.PropertyToID("_BaseMap");

    [SerializeField] NightLoop loop;
    [SerializeField] PhotoPrint photos;
    [Tooltip("The prints in the order they go up; this object's own renderer among them. The last is the one of her asleep.")]
    [SerializeField] Renderer[] prints = new Renderer[0];
    [Tooltip("How many are up at each stage.")]
    [SerializeField] int[] shownAtStage = { 3, 5, 7 };
    [SerializeField] Color paper = new Color(0.88f, 0.86f, 0.8f);
    [Tooltip("The white edge round each print, in photo pixels.")]
    [SerializeField] int border = 8;
    [Tooltip("How far from the lens she stands in them, at the second stage and the third.")]
    [SerializeField] Vector2 herDistance = new Vector2(2.6f, 1.4f);

    [Header("Asleep")]
    [SerializeField] Vector3 asleepEye = new Vector3(0.75f, 2.3f, -0.2f);
    [SerializeField] Vector3 asleepLookAt = new Vector3(2.2f, 0.6f, -0.36f);
    [Tooltip("The player figure's origin, between her feet, once she lies on the bed.")]
    [SerializeField] Vector3 asleepAt = new Vector3(1.3f, 0.75f, -0.36f);
    [SerializeField] Vector3 asleepRotation = new Vector3(-90f, -90f, 0f);

    [Header("When she has taken too few of her own")]
    [SerializeField] Vector3[] spareEyes = { new Vector3(-0.7f, 1.5f, -0.4f), new Vector3(0.6f, 1.5f, -1.2f), new Vector3(-0.9f, 1.5f, 0.3f) };
    [SerializeField] Vector3[] spareTargets = { new Vector3(-0.7f, 1.0f, -3.5f), new Vector3(2.6f, 0.8f, 0.6f), new Vector3(-2.2f, 1.0f, 2.8f) };

    readonly List<PhotoPrint.Shot> chosen = new List<PhotoPrint.Shot>();
    Material[] materials;
    Texture2D[] pictures;
    Collider solid;

    public override int StageCount => shownAtStage.Length;

    void Awake()
    {
        solid = GetComponent<Collider>();
        materials = new Material[prints.Length];
        pictures = new Texture2D[prints.Length];
        for (int i = 0; i < prints.Length; i++)
            materials[i] = prints[i].material;
        Apply(0);
    }

    void OnDestroy()
    {
        foreach (Texture2D picture in pictures)
            Destroy(picture);
        foreach (Material material in materials)
            Destroy(material);
    }

    protected override void Apply(int stage)
    {
        int shown = stage == 0 ? 0 : Mathf.Min(prints.Length, shownAtStage[stage - 1]);
        if (stage == 0)
            chosen.Clear();
        else
            PutUp(stage, shown);
        for (int i = 0; i < prints.Length; i++)
            prints[i].enabled = i < shown;
        solid.enabled = shown > 0;
    }

    public override void CollectParts(List<Bounds> parts)
    {
        foreach (Renderer print in prints)
        {
            if (print.enabled)
                parts.Add(print.bounds);
        }
    }

    // Stages only grow while the screen is black, so all of this is drawn unseen.
    void PutUp(int stage, int shown)
    {
        if (chosen.Count == 0)
            Choose(prints.Length - 1);
        bool asleep = stage == StageCount;
        for (int i = 0; i < shown; i++)
        {
            byte[] pixels;
            if (asleep && i == prints.Length - 1)
                pixels = photos.Asleep(asleepEye, asleepLookAt, asleepAt, Quaternion.Euler(asleepRotation));
            else if (stage == 1)
                pixels = photos.CleanOf(chosen[i]);
            else
                pixels = photos.WithHer(chosen[i], stage == 2 ? herDistance.x : herDistance.y) ?? photos.CleanOf(chosen[i]);
            Show(i, pixels);
        }
    }

    // The player's own, those taken at night first, in no order she would recognise; topped up from the flat itself.
    void Choose(int count)
    {
        var own = new List<PhotoPrint.Shot>();
        foreach (PhotoPrint.Shot shot in photos.Archive)
        {
            if (!shot.Foreign)
                own.Add(shot);
        }
        for (int i = own.Count - 1; i > 0; i--)
        {
            int other = Random.Range(0, i + 1);
            (own[i], own[other]) = (own[other], own[i]);
        }
        own.Sort((a, b) => a.Day.CompareTo(b.Day));
        for (int i = 0; i < own.Count && chosen.Count < count; i++)
        {
            // Kept now: the archive lets old photos go, and this one may be among them by the time she is added to it.
            photos.CleanOf(own[i]);
            chosen.Add(own[i]);
        }
        for (int i = 0; chosen.Count < count; i++)
            chosen.Add(photos.Unseen(spareEyes[i % spareEyes.Length], spareTargets[i % spareTargets.Length]));
    }

    // The part of the frame inside the viewfinder, as the print shows it, on paper with a white edge.
    void Show(int index, byte[] pixels)
    {
        Vector2Int size = photos.Size;
        Rect frame = loop.PhotoFrame;
        int x0 = Mathf.RoundToInt(frame.xMin * size.x);
        int y0 = Mathf.RoundToInt(frame.yMin * size.y);
        int width = Mathf.RoundToInt(frame.width * size.x);
        int height = Mathf.RoundToInt(frame.height * size.y);
        int paperWidth = width + border * 2;
        int paperHeight = height + border * 2;

        Texture2D picture = pictures[index];
        if (picture == null)
        {
            picture = new Texture2D(paperWidth, paperHeight, GraphicsFormat.R8G8B8A8_SRGB, TextureCreationFlags.None)
            {
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp,
            };
            pictures[index] = picture;
            materials[index].SetTexture(BaseMapId, picture);
        }

        var bytes = new byte[paperWidth * paperHeight * 4];
        Color32 edge = paper;
        for (int i = 0; i < bytes.Length; i += 4)
        {
            bytes[i] = edge.r;
            bytes[i + 1] = edge.g;
            bytes[i + 2] = edge.b;
            bytes[i + 3] = 255;
        }
        for (int y = 0; y < height; y++)
            System.Array.Copy(pixels, ((y0 + y) * size.x + x0) * 4, bytes, ((border + y) * paperWidth + border) * 4, width * 4);
        picture.SetPixelData(bytes, 0);
        picture.Apply(false);
    }
}
