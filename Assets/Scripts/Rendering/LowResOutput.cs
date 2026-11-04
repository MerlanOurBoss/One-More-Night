using UnityEngine;
using UnityEngine.UI;

/// <summary>Stretches the low-res image by a whole number; the leftover screen stays black.</summary>
[ExecuteAlways]
[RequireComponent(typeof(RawImage))]
public class LowResOutput : MonoBehaviour
{
    void Update()
    {
        var image = GetComponent<RawImage>();
        if (image.texture == null)
            return;

        int width = image.texture.width;
        int height = image.texture.height;
        int scale = Mathf.Max(1, Mathf.Min(Screen.width / width, Screen.height / height));
        image.rectTransform.sizeDelta = new Vector2(width * scale, height * scale);
    }
}
