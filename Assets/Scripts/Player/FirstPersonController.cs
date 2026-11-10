using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>First-person walking and mouse look, using the project-wide Player actions.</summary>
[RequireComponent(typeof(CharacterController))]
public class FirstPersonController : MonoBehaviour
{
    [SerializeField] Transform view;
    [SerializeField] float walkSpeed = 1.6f;
    [SerializeField] float sprintSpeed = 2.8f;
    [SerializeField] float lookSensitivity = 0.1f;
    [SerializeField] float maxPitch = 80f;

    public bool Frozen { get; set; }
    /// <summary>Degrees per mouse count. Settings change it.</summary>
    public float LookSensitivity { get => lookSensitivity; set => lookSensitivity = value; }
    /// <summary>Mouse up looks down.</summary>
    public bool InvertY { get; set; }

    CharacterController controller;
    InputAction move;
    InputAction look;
    InputAction sprint;
    float pitch;
    float whipTime;
    float whipTurn;
    float whipHeldUntil;
    float whipEnd;
    float whipFromYaw;
    float whipToYaw;
    float whipFromPitch;
    float whipToPitch;

    /// <summary>The head is being jerked round: the player has no say until it is over.</summary>
    public bool Whipping { get; private set; }
    /// <summary>How far the view has closed in during a whip, from 0 to 1.</summary>
    public float WhipZoom { get; private set; }
    /// <summary>The field of view at the closest.</summary>
    public float WhipFieldOfView { get; private set; }

    void Awake()
    {
        controller = GetComponent<CharacterController>();
        move = InputSystem.actions.FindAction("Player/Move", true);
        look = InputSystem.actions.FindAction("Player/Look", true);
        sprint = InputSystem.actions.FindAction("Player/Sprint", true);
        pitch = Mathf.DeltaAngle(0f, view.localEulerAngles.x);
    }

    void OnEnable()
    {
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;
    }

    void OnDisable()
    {
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
    }

    public void Teleport(Vector3 position, float yaw, float newPitch)
    {
        // CharacterController overrides a moved transform while it is enabled.
        controller.enabled = false;
        transform.SetPositionAndRotation(position, Quaternion.Euler(0f, yaw, 0f));
        controller.enabled = true;
        pitch = newPitch;
        view.localRotation = Quaternion.Euler(pitch, 0f, 0f);
    }

    /// <summary>Jerks the view onto a point, fast at first and settling, closes in until this much of the world around it fills the screen from top to bottom, holds, and lets go.</summary>
    public void WhipTo(Vector3 point, float closeUpSize, float turnSeconds, float holdSeconds, float releaseSeconds)
    {
        float distance = Vector3.Distance(point, view.position);
        WhipFieldOfView = 2f * Mathf.Atan2(closeUpSize / 2f, distance) * Mathf.Rad2Deg;
        Vector3 to = (point - view.position).normalized;
        whipFromYaw = transform.eulerAngles.y;
        whipToYaw = Mathf.Atan2(to.x, to.z) * Mathf.Rad2Deg;
        whipFromPitch = pitch;
        whipToPitch = Mathf.Clamp(-Mathf.Asin(to.y) * Mathf.Rad2Deg, -maxPitch, maxPitch);
        whipTurn = turnSeconds;
        whipHeldUntil = turnSeconds + holdSeconds;
        whipEnd = whipHeldUntil + releaseSeconds;
        whipTime = 0f;
        Whipping = true;
    }

    void Whip()
    {
        whipTime += Time.deltaTime;
        float left = 1f - Mathf.Clamp01(whipTime / whipTurn);
        float t = 1f - left * left * left;
        transform.rotation = Quaternion.Euler(0f, Mathf.LerpAngle(whipFromYaw, whipToYaw, t), 0f);
        pitch = Mathf.Lerp(whipFromPitch, whipToPitch, t);
        view.localRotation = Quaternion.Euler(pitch, 0f, 0f);
        WhipZoom = whipTime <= whipHeldUntil ? t : 1f - Mathf.SmoothStep(0f, 1f, (whipTime - whipHeldUntil) / (whipEnd - whipHeldUntil));
        if (whipTime >= whipEnd)
            Whipping = false;
    }

    void Update()
    {
        if (Frozen)
        {
            Whipping = false;
            return;
        }
        if (Whipping)
        {
            Whip();
            return;
        }

        Vector2 lookDelta = look.ReadValue<Vector2>() * lookSensitivity;
        transform.Rotate(0f, lookDelta.x, 0f);
        pitch = Mathf.Clamp(pitch - (InvertY ? -lookDelta.y : lookDelta.y), -maxPitch, maxPitch);
        view.localRotation = Quaternion.Euler(pitch, 0f, 0f);

        Vector2 input = move.ReadValue<Vector2>();
        float speed = sprint.IsPressed() ? sprintSpeed : walkSpeed;
        // SimpleMove applies gravity on its own.
        controller.SimpleMove((transform.right * input.x + transform.forward * input.y) * speed);
    }
}
