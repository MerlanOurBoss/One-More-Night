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

    CharacterController controller;
    InputAction move;
    InputAction look;
    InputAction sprint;
    float pitch;

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

    void Update()
    {
        if (Frozen)
            return;

        Vector2 lookDelta = look.ReadValue<Vector2>() * lookSensitivity;
        transform.Rotate(0f, lookDelta.x, 0f);
        pitch = Mathf.Clamp(pitch - lookDelta.y, -maxPitch, maxPitch);
        view.localRotation = Quaternion.Euler(pitch, 0f, 0f);

        Vector2 input = move.ReadValue<Vector2>();
        float speed = sprint.IsPressed() ? sprintSpeed : walkSpeed;
        // SimpleMove applies gravity on its own.
        controller.SimpleMove((transform.right * input.x + transform.forward * input.y) * speed);
    }
}
