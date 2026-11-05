using System;
using UnityEngine;
using UnityEngine.UI;

/// <summary>Notes left by whoever lived here. At most one a day, always in order, tucked somewhere different each run.</summary>
public class NoteCollection : MonoBehaviour
{
    public const int CodeLength = 4;

    [Serializable]
    public struct Note
    {
        [TextArea(4, 10)] public string text;
        public Color ink;
    }

    [SerializeField] NightLoop loop;
    [SerializeField] FirstPersonController player;
    [SerializeField] NightAudio sound;

    [Header("In order. The first and last note always use the first and last hiding place. {0}-{3} in a text are digits of the safe's code.")]
    [SerializeField] Note[] notes;
    [SerializeField] Collider[] hidingPlaces;

    [Header("Reading")]
    [SerializeField] GameObject sheet;
    [SerializeField] Text sheetText;

    public bool Reading { get; private set; }

    readonly int[] code = new int[CodeLength];
    readonly bool[] digitRead = new bool[CodeLength];
    int[] placeOfNote;
    int notesRead;
    int lastNightRead;
    Collider available;

    void Awake()
    {
        sheet.SetActive(false);
        Clear();
        ShowForToday();
    }

    /// <summary>A new run: nothing read, hiding places shuffled.</summary>
    public void Clear()
    {
        notesRead = 0;
        lastNightRead = 0;
        placeOfNote = new int[notes.Length];
        for (int i = 0; i < placeOfNote.Length; i++)
            placeOfNote[i] = i;
        for (int i = placeOfNote.Length - 2; i > 1; i--)
        {
            int other = UnityEngine.Random.Range(1, i + 1);
            (placeOfNote[i], placeOfNote[other]) = (placeOfNote[other], placeOfNote[i]);
        }
        for (int i = 0; i < CodeLength; i++)
        {
            code[i] = UnityEngine.Random.Range(0, 10);
            digitRead[i] = false;
        }
        Hide();
    }

    public void ShowForToday()
    {
        Hide();
        if (notesRead >= notes.Length || lastNightRead == loop.Night)
            return;
        available = hidingPlaces[placeOfNote[notesRead]];
        available.gameObject.SetActive(true);
    }

    public void Hide()
    {
        available = null;
        foreach (Collider place in hidingPlaces)
            place.gameObject.SetActive(false);
    }

    public bool IsNote(Collider target) => target != null && target == available;

    public bool CodeMatches(int[] digits)
    {
        for (int i = 0; i < CodeLength; i++)
        {
            if (digits[i] != code[i])
                return false;
        }
        return true;
    }

    /// <summary>The code as far as the player has read it, like "4 _ 7 _".</summary>
    public string KnownCode()
    {
        var known = new System.Text.StringBuilder();
        for (int i = 0; i < CodeLength; i++)
            known.Append(digitRead[i] ? code[i].ToString() : "_").Append(i < CodeLength - 1 ? " " : "");
        return known.ToString();
    }

    public void Open()
    {
        Note note = notes[notesRead];
        sheetText.text = string.Format(note.text, code[0], code[1], code[2], code[3]);
        for (int i = 0; i < CodeLength; i++)
            digitRead[i] |= note.text.Contains("{" + i + "}");
        sheetText.color = note.ink;
        sheet.SetActive(true);
        Reading = true;
        player.Frozen = true;
        sound.PlayPaper();
    }

    public void Close()
    {
        sheet.SetActive(false);
        Reading = false;
        player.Frozen = false;
        notesRead++;
        lastNightRead = loop.Night;
        Hide();
    }
}
