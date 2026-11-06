using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

/// <summary>Teaches the controls once: a short chain through the first day and night, plus "E ..." the first time you can use each thing.</summary>
public class ControlHints : MonoBehaviour
{
    enum Step { Walk, Sleep, Aim, Shoot, ViewPhoto, Send, Done }

    [SerializeField] NightLoop loop;
    [SerializeField] NoteCollection notes;
    [SerializeField] SafeLock safeLock;
    [SerializeField] Text hintText;
    [SerializeField] float viewPhotoHintFor = 8f;

    readonly HashSet<string> usedPrompts = new HashSet<string>();
    InputAction move;
    InputAction aim;
    InputAction viewPhoto;
    Step step = Step.Walk;
    float viewPhotoHintUntil;

    void Awake()
    {
        move = InputSystem.actions.FindAction("Player/Move", true);
        aim = InputSystem.actions.FindAction("Player/Aim", true);
        viewPhoto = InputSystem.actions.FindAction("Player/ViewPhoto", true);
    }

    public void MarkUsed(string prompt) => usedPrompts.Add(prompt);

    public void PhotoTaken()
    {
        if (step > Step.ViewPhoto)
            return;
        step = Step.ViewPhoto;
        viewPhotoHintUntil = Time.time + viewPhotoHintFor;
    }

    void Update()
    {
        string hint = Pick();
        hintText.text = hint;
        hintText.enabled = hint.Length > 0;
    }

    string Pick()
    {
        if (!loop.Started || loop.CurrentPhase == NightLoop.Phase.Transition || safeLock.Busy || loop.AtDesk || loop.Peeping)
            return "";
        if (notes.Reading)
            return "E закрыть";

        Advance();
        string prompt = loop.UsePrompt;
        if (prompt != null && !usedPrompts.Contains(prompt))
            return "E " + prompt;

        bool night = loop.CurrentPhase == NightLoop.Phase.Night;
        switch (step)
        {
            case Step.Walk: return "WASD идти   Shift бежать";
            case Step.Sleep: return "Ляг на кровать, когда будешь готов";
            case Step.Aim: return night ? "Что-то изменилось. ПКМ поднять камеру" : "";
            case Step.Shoot:
                if (!night)
                    return "";
                return aim.IsPressed() ? "ЛКМ снять" : "ПКМ поднять камеру";
            case Step.ViewPhoto: return "Зажми Q, чтобы рассмотреть снимок";
            case Step.Send: return night ? "" : "Отправь снимки с компьютера на кухне. Пустой кадр штраф";
            default: return "";
        }
    }

    void Advance()
    {
        switch (step)
        {
            case Step.Walk:
                if (move.ReadValue<Vector2>().sqrMagnitude > 0.01f)
                    step = Step.Sleep;
                break;
            case Step.Sleep:
                if (loop.CurrentPhase == NightLoop.Phase.Night)
                    step = Step.Aim;
                break;
            case Step.Aim:
                if (aim.IsPressed())
                    step = Step.Shoot;
                break;
            case Step.ViewPhoto:
                if (viewPhoto.IsPressed() || Time.time > viewPhotoHintUntil)
                    step = Step.Send;
                break;
            case Step.Send:
                if (!loop.HasUnsentPhotos)
                    step = Step.Done;
                break;
        }
    }
}
