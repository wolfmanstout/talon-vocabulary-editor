import re
import time
from typing import Union

from talon import Context, Module, actions
from talon.grammar import Phrase

from .parse_phrase import parse_phrase
from .user_settings import append_to_csv, get_list_from_csv

mod = Module()
ctx = Context()

vocabulary_recording_dir = mod.setting(
    "vocabulary_recording_dir",
    type=str,
    default=None,
    desc="If specified, log vocabulary recordings to this directory.",
)

mod.mode("vocabulary_test", "a mode used internally to test vocabulary words")
mod.list(
    "vocabulary_keys",
    desc="spoken forms of additional vocabulary words, used internally for testing",
)
test_result: str = ""


@mod.capture(rule="({user.vocabulary_keys} | <phrase>)")
def vocabulary_test_phrase(m) -> str:
    """User defined spoken forms or phrase."""
    try:
        return m.vocabulary_keys
    except AttributeError:
        return " ".join(actions.dictate.parse_words(m.phrase))


@mod.action_class
class Actions:
    def test_vocabulary_phrase(result: str):
        """Tests the recognition of the phrase."""
        global test_result
        test_result = result


def _get_spoken_form_from_test(
    default_spoken_form: str, phrase: Phrase, phrases: dict[str, str]
) -> str:
    global test_result
    test_result = ""
    vocabulary_keys = set(phrases.keys())
    vocabulary_keys.add(default_spoken_form)
    ctx.lists["user.vocabulary_keys"] = vocabulary_keys
    actions.mode.save()
    try:
        actions.mode.disable("command")
        actions.mode.disable("dictation")
        actions.mode.enable("user.vocabulary_test")
        if vocabulary_recording_dir.get():
            recording_path = "{}/{}_{}.flac".format(
                vocabulary_recording_dir.get(),
                re.sub(r"[^A-Za-z]", "_", default_spoken_form),
                round(time.time()),
            )
        else:
            recording_path = ""
        parse_phrase(phrase, recording_path)
    finally:
        actions.mode.restore()
        spoken_form = test_result
        test_result = ""
    return spoken_form


def _create_vocabulary_entries(spoken_form, written_form, type):
    """Expands the provided spoken form and written form into multiple variants based on
    the provided type, which can be either "name" to add a possessive variant or "noun"
    to add plural.
    """
    entries = {spoken_form: written_form}
    if type == "name":
        # Note that we use the spoken form without apostrophe because this seems to generally lead
        # to better recognition on Conformer b108.
        entries[f"{spoken_form}s"] = f"{written_form}'s"
    elif type == "noun":
        # Note that we simply append an "s", but we could use something more sophisticated like
        # https://github.com/jpvanhal/inflection. The downside is that this is less predictable,
        # and this feature is likely to be used in ways that are unlike common English prose, which
        # is already included in the lexicon. For example, made up identifiers used in programming.
        entries[f"{spoken_form}s"] = f"{written_form}s"
    return entries


def _add_selection_to_csv(
    phrase: Union[Phrase, str],
    type: str,
    csv: str,
    csv_contents: dict[str, str],
    skip_identical_replacement: bool,
    try_default_spoken_form: bool,
):
    written_form = actions.edit.selected_text().strip()
    is_acronym = re.fullmatch(r"[A-Z]+", written_form)
    default_spoken_form = " ".join(written_form) if is_acronym else written_form
    if phrase:
        if try_default_spoken_form and isinstance(phrase, Phrase):
            spoken_form = _get_spoken_form_from_test(
                default_spoken_form, phrase, csv_contents
            )
        else:
            spoken_form = " ".join(actions.dictate.parse_words(phrase))
    else:
        spoken_form = default_spoken_form
    entries = _create_vocabulary_entries(spoken_form, written_form, type)
    new_entries = {}
    added_some_phrases = False
    for spoken_form, written_form in entries.items():
        if skip_identical_replacement and spoken_form == written_form:
            actions.app.notify(f'Skipping identical replacement: "{spoken_form}"')
        elif spoken_form in csv_contents:
            actions.app.notify(f'Spoken form "{spoken_form}" is already in {csv}')
        else:
            new_entries[spoken_form] = written_form
            added_some_phrases = True
    append_to_csv(csv, new_entries)
    if added_some_phrases:
        actions.app.notify(f"Added to {csv}: {new_entries}")


@ctx.action_class("user")
class OverwrittenActions:
    def add_selection_to_vocabulary(phrase: Union[Phrase, str] = "", type: str = ""):
        vocabulary = get_list_from_csv(
            "additional_words.csv",
            headers=("Word(s)", "Spoken Form (If Different)"),
        )
        _add_selection_to_csv(
            phrase,
            type,
            "additional_words.csv",
            vocabulary,
            skip_identical_replacement=False,
            try_default_spoken_form=True,
        )

    def add_selection_to_words_to_replace(phrase: Phrase, type: str = ""):
        phrases_to_replace = get_list_from_csv(
            "words_to_replace.csv",
            headers=("Replacement", "Original"),
        )
        _add_selection_to_csv(
            phrase,
            type,
            "words_to_replace.csv",
            phrases_to_replace,
            skip_identical_replacement=True,
            try_default_spoken_form=False,
        )
