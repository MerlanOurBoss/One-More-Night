using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>
/// Esc during a run: time and sound stop, and a short menu comes up, with settings that are kept between launches.
/// Read straight from the keyboard and mouse: the player's own controls are switched off while it is open.
/// </summary>
public class PauseMenu : MonoBehaviour
{
    const string VolumeKey = "settings.volume";
    const string SensitivityKey = "settings.sensitivity";
    const string InvertKey = "settings.invertY";

    enum Page { Main, Settings }

    [SerializeField] NightLoop loop;
    [SerializeField] FirstPersonController player;
    [SerializeField] GameObject screen;
    [SerializeField] Text heading;
    [Tooltip("One line each, top to bottom. The longest page sets how many are needed.")]
    [SerializeField] Text[] rows = new Text[0];
    [SerializeField] Text footer;
    [SerializeField] Color idle = new Color(0.55f, 0.55f, 0.55f);
    [SerializeField] Color selected = Color.white;
    [Tooltip("Plays while everything else is paused.")]
    [SerializeField] AudioSource clicks;
    [SerializeField] AudioClip move;

    [Header("Ranges")]
    [SerializeField] float sensitivityMin = 0.25f;
    [SerializeField] float sensitivityMax = 3f;
    [SerializeField] float sensitivityStep = 0.25f;

    /// <summary>While true, nothing in the game should take input of its own.</summary>
    public static bool Paused { get; private set; }

    InputActionMap playerControls;
    Page page;
    int selection;
    int confirming = -1;
    float timeScale = 1f;
    float baseSensitivity;
    float volume = 1f;
    float sensitivity = 1f;
    bool invertY;
    Vector2 lastMouse;

    void Awake()
    {
        playerControls = InputSystem.actions.FindActionMap("Player", true);
        baseSensitivity = player.LookSensitivity;
        volume = PlayerPrefs.GetFloat(VolumeKey, 1f);
        sensitivity = PlayerPrefs.GetFloat(SensitivityKey, 1f);
        invertY = PlayerPrefs.GetInt(InvertKey, 0) == 1;
        ApplySettings();
        clicks.ignoreListenerPause = true;
        screen.SetActive(false);
        Paused = false;
    }

    void OnDestroy()
    {
        // Leaving play mode or the scene while paused must not leave the world stopped.
        if (Paused)
            Resume();
    }

    void Update()
    {
        Keyboard keys = Keyboard.current;
        if (keys == null)
            return;

        if (!Paused)
        {
            // The title and the intro have their own Esc.
            if (keys.escapeKey.wasPressedThisFrame && loop.Started)
                Pause();
            return;
        }

        if (keys.escapeKey.wasPressedThisFrame)
        {
            if (page == Page.Settings)
                OpenPage(Page.Main, 1);
            else
                Resume();
            return;
        }

        int count = RowCount;
        if (keys.wKey.wasPressedThisFrame || keys.upArrowKey.wasPressedThisFrame)
            Select((selection + count - 1) % count);
        else if (keys.sKey.wasPressedThisFrame || keys.downArrowKey.wasPressedThisFrame)
            Select((selection + 1) % count);
        else if (keys.aKey.wasPressedThisFrame || keys.leftArrowKey.wasPressedThisFrame)
            Change(-1);
        else if (keys.dKey.wasPressedThisFrame || keys.rightArrowKey.wasPressedThisFrame)
            Change(1);
        else if (keys.enterKey.wasPressedThisFrame || keys.numpadEnterKey.wasPressedThisFrame || keys.eKey.wasPressedThisFrame || keys.spaceKey.wasPressedThisFrame)
            Activate(0);

        ReadMouse();
    }

    void ReadMouse()
    {
        Mouse mouse = Mouse.current;
        if (mouse == null)
            return;
        Vector2 at = mouse.position.ReadValue();
        Camera eye = screen.GetComponentInParent<Canvas>().worldCamera;
        int under = -1;
        for (int i = 0; i < RowCount; i++)
        {
            if (RectTransformUtility.RectangleContainsScreenPoint(rows[i].rectTransform, at, eye))
                under = i;
        }
        // Only a mouse that moves takes the selection from the keys.
        if (under >= 0 && (at - lastMouse).sqrMagnitude > 1f && under != selection)
            Select(under);
        lastMouse = at;
        if (under < 0)
            return;

        float scroll = mouse.scroll.ReadValue().y;
        if (scroll != 0f && IsValueRow(under))
            Change(scroll > 0f ? 1 : -1);
        if (mouse.leftButton.wasPressedThisFrame)
        {
            Select(under);
            // On a value, the left half of the line turns it down and the right half up.
            RectTransformUtility.ScreenPointToLocalPointInRectangle(rows[under].rectTransform, at, eye, out Vector2 local);
            Activate(local.x < 0f ? -1 : 1);
        }
    }

    void Pause()
    {
        Paused = true;
        timeScale = Time.timeScale;
        Time.timeScale = 0f;
        AudioListener.pause = true;
        playerControls.Disable();
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
        lastMouse = Mouse.current != null ? Mouse.current.position.ReadValue() : Vector2.zero;
        screen.SetActive(true);
        OpenPage(Page.Main, 0);
    }

    void Resume()
    {
        Paused = false;
        Time.timeScale = timeScale;
        AudioListener.pause = false;
        playerControls.Enable();
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;
        screen.SetActive(false);
    }

    // Both pages have four lines.
    const int RowCount = 4;

    bool IsValueRow(int row) => page == Page.Settings && row < 3;

    void OpenPage(Page next, int row)
    {
        page = next;
        confirming = -1;
        heading.text = page == Page.Main ? "Пауза" : "Настройки";
        footer.text = page == Page.Main ? "W/S выбрать   E выбрать   Esc продолжить" : "W/S выбрать   A/D изменить   Esc назад";
        for (int i = 0; i < rows.Length; i++)
            rows[i].gameObject.SetActive(i < RowCount);
        Select(row, false);
    }

    void Select(int row, bool click = true)
    {
        if (row != selection)
            confirming = -1;
        selection = row;
        if (click)
            Click();
        Redraw();
    }

    // direction: 0 from a key, or which half of the line the mouse pressed.
    void Activate(int direction)
    {
        if (page == Page.Settings)
        {
            if (selection == 3)
            {
                OpenPage(Page.Main, 1);
                Click();
            }
            else
                Change(direction == 0 ? 1 : direction);
            return;
        }

        switch (selection)
        {
            case 0:
                Resume();
                break;
            case 1:
                OpenPage(Page.Settings, 0);
                Click();
                break;
            case 2:
            case 3:
                // Both lose the run: ask once more.
                if (confirming != selection)
                {
                    confirming = selection;
                    Click();
                    Redraw();
                    return;
                }
                if (selection == 2)
                {
                    Resume();
                    loop.QuitToTitle();
                }
                else
                    Quit();
                break;
        }
    }

    void Change(int direction)
    {
        if (!IsValueRow(selection))
            return;
        switch (selection)
        {
            case 0:
                volume = Mathf.Clamp01(Mathf.Round((volume + 0.1f * direction) * 10f) / 10f);
                break;
            case 1:
                sensitivity = Mathf.Clamp(sensitivity + sensitivityStep * direction, sensitivityMin, sensitivityMax);
                break;
            case 2:
                invertY = !invertY;
                break;
        }
        ApplySettings();
        PlayerPrefs.SetFloat(VolumeKey, volume);
        PlayerPrefs.SetFloat(SensitivityKey, sensitivity);
        PlayerPrefs.SetInt(InvertKey, invertY ? 1 : 0);
        PlayerPrefs.Save();
        Click();
        Redraw();
    }

    void ApplySettings()
    {
        AudioListener.volume = volume;
        player.LookSensitivity = baseSensitivity * sensitivity;
        player.InvertY = invertY;
    }

    void Redraw()
    {
        string[] labels = page == Page.Main
            ? new[] { "Продолжить", "Настройки", confirming == 2 ? "Выйти в меню? Забег пропадёт" : "Выйти в меню", confirming == 3 ? "Выйти из игры? Забег пропадёт" : "Выйти из игры" }
            // The pixel font has no < >: guillemets mark what A/D turn.
            : new[] { "Громкость   « " + Mathf.RoundToInt(volume * 100f) + "% »", "Чувствительность мыши   « " + sensitivity.ToString("0.00") + " »", "Инверсия мыши   « " + (invertY ? "вкл" : "выкл") + " »", "Назад" };
        for (int i = 0; i < labels.Length && i < rows.Length; i++)
        {
            rows[i].text = labels[i];
            rows[i].color = i == selection ? selected : idle;
        }
    }

    void Click()
    {
        if (move != null)
            clicks.PlayOneShot(move);
    }

    static void Quit()
    {
#if UNITY_EDITOR
        UnityEditor.EditorApplication.isPlaying = false;
#else
        Application.Quit();
#endif
    }
}
