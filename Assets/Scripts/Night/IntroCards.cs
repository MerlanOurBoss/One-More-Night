using System;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>
/// A few cards before the first day: who you are, what to do, and what happens if you don't.
/// Each one drifts the camera through its own corner of the flat while the words write themselves in. E hurries the text, then turns the card; Esc skips.
/// </summary>
public class IntroCards : MonoBehaviour
{
    [Serializable]
    public class Card
    {
        [Tooltip("{0} is the goal, {1} the last night the door still lets you out.")]
        [TextArea(2, 4)] public string text;
        [Tooltip("The camera drifts from here to there, looking from one point to the other, over the card's shot.")]
        public Vector3 from;
        public Vector3 to;
        public Vector3 lookFrom;
        public Vector3 lookTo;
        [Tooltip("Shown by night light.")]
        public bool night;
        [Tooltip("Stands in the shot at this stage, and is gone again when the intro ends.")]
        public Anomaly anomaly;
        public int stage = 1;
        [Tooltip("Heard once, a moment into the card, from where the camera ends up looking.")]
        public AudioClip sound;
        public float soundDelay = 1f;
    }

    enum State { FadingIn, Card, FadingOut, Leaving }

    [Header("Scene")]
    [SerializeField] NightLoop loop;
    [SerializeField] Transform view;
    [SerializeField] NightAudio sound;

    [Header("Screen")]
    [SerializeField] GameObject screen;
    [Tooltip("Darkens the shot behind the text, and goes black between cards.")]
    [SerializeField] Image overlay;
    [SerializeField] GameObject[] bars = new GameObject[0];
    [SerializeField] Text body;
    [SerializeField] Text page;

    [Header("Timing")]
    [SerializeField] float shotSeconds = 10f;
    [SerializeField] float fadeSeconds = 0.5f;
    [SerializeField] float leaveSeconds = 1.2f;
    [SerializeField, Range(0f, 1f)] float dim = 0.3f;
    [SerializeField] float lettersPerSecond = 28f;
    [Tooltip("How many letters are still coming up at once.")]
    [SerializeField] float letterFade = 5f;
    [SerializeField] float pauseAtLineEnd = 0.35f;
    [SerializeField] float pauseAtFullStop = 0.25f;

    [SerializeField] Card[] cards = new Card[0];

    InputAction interact;
    State state;
    int index;
    bool finishing;
    int openedOnFrame;
    float stateStarted;
    float cardStarted;
    float textStarted;
    string text;
    float[] letterTimes;
    string goal;
    string lastNight;
    Anomaly shown;
    float soundAt = float.PositiveInfinity;
    Vector3 viewLocalPosition;
    Quaternion viewLocalRotation;
    Action onDone;
    readonly StringBuilder built = new StringBuilder();

    public bool Showing { get; private set; }

    void Awake()
    {
        interact = InputSystem.actions.FindAction("Player/Interact", true);
        screen.SetActive(false);
    }

    public void Show(int goalMoney, int lastNightDoorOpens, Action done)
    {
        goal = goalMoney.ToString();
        lastNight = lastNightDoorOpens.ToString();
        onDone = done;
        viewLocalPosition = view.localPosition;
        viewLocalRotation = view.localRotation;
        openedOnFrame = Time.frameCount;
        finishing = false;
        Showing = true;
        screen.SetActive(true);
        SetBars(true);
        overlay.color = Color.black;
        index = 0;
        StartCard();
    }

    void Update()
    {
        if (!Showing)
            return;

        float k = Mathf.Clamp01((Time.time - stateStarted) / (state == State.Leaving ? leaveSeconds : fadeSeconds));
        switch (state)
        {
            case State.FadingIn:
                SetDarkness(Mathf.Lerp(1f, dim, k));
                if (k >= 1f)
                    SetState(State.Card);
                break;
            case State.FadingOut:
                SetDarkness(Mathf.Lerp(dim, 1f, k));
                if (k >= 1f)
                    NextCard();
                // The camera is home again: nothing more to drift or write.
                if (state == State.Leaving)
                    return;
                break;
            case State.Leaving:
                SetDarkness(1f - k);
                if (k >= 1f)
                    Done();
                return;
        }

        Drift();
        WriteText();
        if (Time.time >= soundAt)
        {
            soundAt = float.PositiveInfinity;
            AudioSource.PlayClipAtPoint(cards[index].sound, cards[index].lookTo);
        }
        if (Time.frameCount != openedOnFrame && (state == State.FadingIn || state == State.Card))
            ReadInput();
    }

    void ReadInput()
    {
        if (Keyboard.current != null && Keyboard.current.escapeKey.wasPressedThisFrame)
        {
            finishing = true;
            SetState(State.FadingOut);
        }
        else if (interact.WasPressedThisFrame())
        {
            // The first E finishes the line; the next one turns the card.
            if (Time.time - textStarted < letterTimes[letterTimes.Length - 1] + letterFade / lettersPerSecond)
                textStarted = Time.time - letterTimes[letterTimes.Length - 1] - letterFade / lettersPerSecond;
            else
            {
                finishing = index == cards.Length - 1;
                SetState(State.FadingOut);
            }
        }
    }

    void NextCard()
    {
        if (finishing)
        {
            // Back to the bedroom, by day, and the dark lifts onto the first morning.
            Restore();
            body.text = "";
            page.text = "";
            SetBars(false);
            SetState(State.Leaving);
            return;
        }
        index++;
        StartCard();
    }

    void StartCard()
    {
        Card card = cards[index];
        loop.PreviewNight(card.night);
        sound.IntroNight = card.night;
        soundAt = card.sound != null ? Time.time + card.soundDelay : float.PositiveInfinity;
        if (shown != null && shown != card.anomaly)
            shown.Clear();
        shown = card.anomaly;
        cardStarted = Time.time;
        Drift();
        if (shown != null)
        {
            while (shown.Stage > card.stage)
                shown.Clear();
            if (shown.Stage == 0)
                shown.Begin();
            while (shown.Stage < card.stage && shown.Develop()) { }
            // She has been watching the lens all along.
            foreach (HeadWatch head in shown.GetComponentsInChildren<HeadWatch>())
                head.LookAtEyeNow();
        }

        text = string.Format(card.text, goal, lastNight);
        letterTimes = new float[text.Length];
        float t = 0.3f;
        for (int i = 0; i < text.Length; i++)
        {
            letterTimes[i] = t;
            t += 1f / lettersPerSecond;
            if (text[i] == '\n')
                t += pauseAtLineEnd;
            else if (text[i] == '.' || text[i] == ',')
                t += pauseAtFullStop;
        }
        textStarted = Time.time;
        page.text = (index + 1) + " / " + cards.Length + "      E дальше   Esc пропустить";
        if (index > 0)
            sound.PlayPaper();
        SetState(State.FadingIn);
    }

    void Drift()
    {
        Card card = cards[index];
        float t = Mathf.Clamp01((Time.time - cardStarted) / shotSeconds);
        // Already moving when it fades in, and slowing as if settling on something.
        t = 1f - (1f - t) * (1f - t);
        Vector3 eye = Vector3.Lerp(card.from, card.to, t);
        Vector3 look = Vector3.Lerp(card.lookFrom, card.lookTo, t);
        view.SetPositionAndRotation(eye, Quaternion.LookRotation(look - eye));
    }

    // Each letter comes up out of the dark a little after the one before; the ones still to come hold their place, so nothing shifts.
    void WriteText()
    {
        float now = Time.time - textStarted;
        built.Length = 0;
        int i = 0;
        while (i < text.Length)
        {
            float a = Mathf.Clamp01((now - letterTimes[i]) * lettersPerSecond / letterFade);
            if (a >= 1f)
            {
                built.Append(text[i]);
                i++;
            }
            else if (a > 0f)
            {
                built.Append("<color=#FFFFFF").Append(((int)(a * 255f)).ToString("X2")).Append('>').Append(text[i]).Append("</color>");
                i++;
            }
            else
            {
                built.Append("<color=#FFFFFF00>").Append(text, i, text.Length - i).Append("</color>");
                break;
            }
        }
        body.text = built.ToString();
    }

    void SetState(State next)
    {
        state = next;
        stateStarted = Time.time;
    }

    void SetDarkness(float amount) => overlay.color = new Color(0f, 0f, 0f, amount);

    void SetBars(bool on)
    {
        foreach (GameObject bar in bars)
            bar.SetActive(on);
    }

    void Restore()
    {
        loop.PreviewNight(false);
        sound.IntroNight = false;
        soundAt = float.PositiveInfinity;
        if (shown != null)
            shown.Clear();
        shown = null;
        view.localPosition = viewLocalPosition;
        view.localRotation = viewLocalRotation;
    }

    void Done()
    {
        Showing = false;
        screen.SetActive(false);
        onDone?.Invoke();
    }
}
