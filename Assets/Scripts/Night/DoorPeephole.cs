using System.Collections;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>The peephole in the front door. The stairwell is always empty. Once, by day, it is not.</summary>
[RequireComponent(typeof(Collider))]
public class DoorPeephole : MonoBehaviour
{
    [SerializeField] NightLoop loop;
    [SerializeField] FirstPersonController player;
    [SerializeField] NightAudio sound;
    [SerializeField] GameObject overlay;
    [SerializeField] RawImage lens;
    [SerializeField] Texture empty;
    [SerializeField] Texture someone;
    [SerializeField] Color nightTint = new Color(0.28f, 0.28f, 0.32f);
    [Tooltip("At night there is sometimes someone too.")]
    [SerializeField] float nightChance = 0.12f;
    [Tooltip("The day someone stands there is picked from these mornings, counting the first day as 1.")]
    [SerializeField] int earliestMorning = 3;
    [SerializeField] int latestMorning = 5;

    InputAction interact;
    InputAction aim;
    int openedOnFrame;
    int closedOnFrame = -1;
    int someoneMorning;
    bool seen;
    bool knockAfter;

    public bool Looking { get; private set; }
    public bool JustClosed => Time.frameCount == closedOnFrame;

    void Awake()
    {
        interact = InputSystem.actions.FindAction("Player/Interact", true);
        aim = InputSystem.actions.FindAction("Player/Aim", true);
        overlay.SetActive(false);
        Clear();
    }

    /// <summary>A new run: a new morning for someone to be standing there.</summary>
    public void Clear()
    {
        someoneMorning = Random.Range(earliestMorning, latestMorning + 1);
        seen = false;
        knockAfter = false;
    }

    public void Look()
    {
        bool day = loop.CurrentPhase == NightLoop.Phase.Day;
        bool there = day ? !seen && loop.Night == someoneMorning : Random.value < nightChance;
        if (there && day)
            seen = true;
        lens.texture = there ? someone : empty;
        lens.color = day ? Color.white : nightTint;
        overlay.SetActive(true);
        Looking = true;
        player.Frozen = true;
        openedOnFrame = Time.frameCount;
        knockAfter = there;
        sound.PlayShutterEmpty();
    }

    void Update()
    {
        if (!Looking || Time.frameCount == openedOnFrame)
            return;
        if (interact.WasPressedThisFrame() || aim.WasPressedThisFrame())
            Close();
    }

    public void Close()
    {
        overlay.SetActive(false);
        Looking = false;
        closedOnFrame = Time.frameCount;
        player.Frozen = false;
        if (knockAfter)
        {
            knockAfter = false;
            StartCoroutine(KnockLater());
        }
    }

    // You stepped back from the door. It knows.
    IEnumerator KnockLater()
    {
        yield return new WaitForSeconds(1.4f);
        sound.PlayKnock();
    }
}
