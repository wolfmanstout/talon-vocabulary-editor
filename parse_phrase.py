# From https://github.com/AndreasArvidsson/andreas-talon/blob/3631f25d426a9fb7526c240cb0c9961ea90072c2/andreas/misc/rephrase.py
from typing import Union

from talon import speech_system
from talon.grammar import Phrase
from talon.lib import flac

phrase_stack = []


def on_pre_phrase(d):
    phrase_stack.append(d)


def on_post_phrase(d):
    phrase_stack.pop()


speech_system.register("pre:phrase", on_pre_phrase)
speech_system.register("post:phrase", on_post_phrase)


def parse_phrase(phrase: Union[Phrase, str], recording_path: str = ""):
    """Rerun phrase"""
    if phrase == "":
        return
    current_phrase = phrase_stack[-1]
    ts = current_phrase["_ts"]
    # Add padding for Conformer D. Value determined experimentally.
    start = phrase.words[0].start - ts - 0.3
    end = phrase.words[-1].end - ts
    samples = current_phrase["samples"]
    pstart = int(start * 16_000)
    pend = int(end * 16_000)
    samples = samples[pstart:pend]
    if recording_path:
        flac.write_file(recording_path, samples)
    speech_system._on_audio_frame(samples)
