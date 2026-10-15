"""English and Hindi word lists for the word-list share signal (plan §4.2 step 1).

A small built-in core (common words and court vocabulary) always loads, so the signal works offline and gives the same
answer on every machine. Fuller lists are added when present: `data/wordlists/en.txt` and `hi.txt` (one word per line)
or the system's `/usr/share/dict/words`. Set `VS_WORDLISTS` to a path-separated list of extra files to use others.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

_EN_CORE = """
a about above across act acts after again against age aged ago all allow allowed also although always am among an and
another any appear appeared applicant application applications applied apply are argued argument arguments around
arrest arrested arrests as at attached authority available bail bailable be became because been before being below
bench between both but by called can case cases certain certificate charge charged charges charging chargesheet
cognisable cognizable commit committed complainant complaint concerned conduct considered contends contention copy
could counsel court courts crime criminal custody date dated dates day days deceased decided declined defence defense
delay denied dated deposition detail details did directed direction disposed dismissed district do document documents
does done due during each earlier either enlarged entitled evidence examination examined except facts false family
father file filed final find fir first following for found four from further given grant granted grounds had has have
having he hearing held her here him his hold honble hon hospital however husband i identity if impugned in inquiry
incident including inspector into investigating investigation is issued it its judge judgment judicial jail
jurisdiction justice kept known late law lawyer learned least led legal less liberty life like made magistrate
make material matter may me medical memo mentioned merits minor month months more most mother much must my name
narrated nature near necessary need neither never no nominal nor not note noted notice now number of offence offences
officer on once one only open opposed or order ordered orders other otherwise our out over own page paper parties party
passed past pending period person petition petitioner place plea police possible post present presented prima facie
prior prison prisoner produced prosecution proceeded proceedings proper provisions public pursuant questions
quantity read reason reasons received record recorded refused regard registered rejected relevant relied remand
remanded remains report reported respect respondent rest result retained returned right rights roll rule said same
sanction saw say second section sections seen sentence served session sessions set several shall she should show
shown side signed since six so some sought special specific state stated statement station status stay still
submissions submitted subject such sufficient suit superintendent surety suspect taken than that the their them then
there therefore these they third this those three through time to together told took trial true two under unless
until upon us use used using various versus very victim view was way we well were what when where whether which while
who whom whose why will with within without witness witnesses would written year years yet you your sir madam
about accordingly adjourned advocate affidavit allegations allege alleged alleges anticipatory antecedents appear
appellant appeal appearance apprehension arrested attendance authorised bailed behalf belief believe benefit bond
bonds brief calendar cancelled cannot capacity carried cause cell certified challan circumstances clause close
co-accused coaccused collected commission common compliance conditions confession confined conviction cooperate
cooperation copies cr crpc ipc bns bnss ndps uapa pmla pocso delhi mumbai chennai kolkata high supreme sessions
dated deponent deposed discharge discharged discretion dismissal disposal dispute duly effect either emergency
enclosed ensure entire essentially established exceed exceeding extended extension fact fair fear fide filing fine
fixed flight forthwith forward free fresh gravity guilt guilty handed heard heinous hereby herein hereinafter
identified imprisonment imposed impose incarcerated indian inform informant information injury innocence innocent
instant interim interrogation investigated jurisprudence juvenile kindly lodged lodging magnitude mandatory maximum
medico mere merely minimum modified monitoring murder next nominal notified objection objections observations
observed obtained occurrence offender omission operative opinion opportunity original outcome paragraph paras para
parity pass pay peace penal penalty permission personal photograph physical plaintiff pleased police posted
practical precedent premises prayer preliminary presence prevent previous principle principles procedure process
production prolonged prompt proof property prosecuted protection prove provided provision purpose put rape
reasonable recall receipt recovery recovered refer referred reflect relation release released relief reliance
remain remarks remedy repeat replied reply requested required requirement reserve residence respectfully
responsible restrictions retrial review revision satisfied schedule scheme search seized seizure sense serious
service sessions settled shown signature similarly situation social solemnly sole stage standing statute statutory
stayed stolen strict strong subsequent substantial succeeding suffering suggest summons support supporting surrender
suspicion sustained tampering tender term terms test thereafter thereby therein thereof thereon threat threatened
trace transfer treated treatment triable tribunal true trust truth undertaking undertrial unlawful urgent vacation
valid verify verified version violation voluntarily warrant warrants week weeks wife without wrongful
""".split()

_HI_CORE = """
का की के को में से पर और है हैं था थी थे ने यह वह इस उस एक दो तीन चार पांच छह सात आठ नौ दस कि जो तो भी ही नहीं या लिए
साथ द्वारा तथा एवं न्यायालय अभियुक्त आरोपी गिरफ्तार गिरफ्तारी जमानत आवेदन आदेश धारा थाना प्राथमिकी रिपोर्ट दिनांक
सूचना शिकायतकर्ता गवाह पुलिस रिमांड न्यायिक अभिरक्षा हिरासत जेल मामला मामले प्रकरण अपराध अपराधिक आपराधिक जाँच जांच
विवेचना आरोप पत्र आरोपपत्र चालान सत्र न्यायाधीश मजिस्ट्रेट अधिवक्ता वकील प्रार्थी प्रार्थना निवेदन सुनवाई पेश प्रस्तुत
उपस्थित हुआ हुई हुए किया किये किया गया गई गए गया थाने थानाध्यक्ष निरीक्षक उप आयोग समय बजे दिन रात माह वर्ष
सन अनुसार विरुद्ध राज्य सरकार प्रति पता निवासी पुत्र पुत्री पत्नी पति पिता माता ग्राम जिला तहसील मोबाइल नंबर संख्या
अंतर्गत संहिता भारतीय दण्ड न्याय सुरक्षा नागरिक घटना घटित स्थान स्थल बयान कथन अंकित दर्ज पंजीकृत प्रथम सूचना मेडिकल
चिकित्सा अस्पताल उपचार स्वास्थ्य बीमार आयु उम्र बच्चे परिवार शपथ पत्र हलफनामा प्रमाणित हस्ताक्षर प्रति अग्रिम नियमित
खारिज स्वीकार मंजूर अस्वीकार निरस्त रद्द पारित आज कल पूर्व पश्चात बाद पहले इसके उसके मेरे हमारे आपके उनके कृपया
अतः अतएव किन्तु परन्तु लेकिन क्योंकि यदि तब जब अब यहाँ वहाँ कहाँ कैसे क्यों कौन क्या कोई सभी सब कुछ बहुत अधिक कम
""".split()

_STEMS = ("s", "es", "ed", "d", "ing", "ly", "al")
_EN_TOKEN = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")
_HI_TOKEN = re.compile(r"[ऀ-ॣ०-ॿ]+")
_DEVANAGARI_START = re.compile(r"^[ऄ-हक़-य़ॲ-ॿ]")
_DOUBLE_SIGN = re.compile(r"[ा-ौॢॣ]{2}")


def _read_words(path: Path) -> set[str]:
    try:
        return {w.strip().lower() for w in path.read_text(encoding="utf-8", errors="ignore").splitlines() if w.strip()}
    except OSError:
        return set()


def _external_files() -> list[Path]:
    extra = [Path(p) for p in os.environ.get("VS_WORDLISTS", "").split(os.pathsep) if p]
    defaults = [Path("data/wordlists/en.txt"), Path("data/wordlists/hi.txt"), Path("/usr/share/dict/words")]
    return [p for p in [*defaults, *extra] if p.is_file()]


@lru_cache(maxsize=1)
def english_words() -> frozenset[str]:
    """Lower-case English words: the built-in core plus any word-list files found."""
    words = {w.lower() for w in _EN_CORE}
    for path in _external_files():
        words |= {w for w in _read_words(path) if w.isascii() and w.isalpha()}
    return frozenset(words)


@lru_cache(maxsize=1)
def hindi_words() -> frozenset[str]:
    """Hindi words: the built-in core plus any word-list files found."""
    words = set(_HI_CORE)
    for path in _external_files():
        words |= {w for w in _read_words(path) if _HI_TOKEN.fullmatch(w)}
    return frozenset(words)


def _known_english(token: str) -> bool:
    words = english_words()
    low = token.lower().removesuffix("'s")
    if low in words:
        return True
    return any(low.endswith(s) and low[: -len(s)] in words for s in _STEMS if len(low) > len(s) + 2)


def _valid_devanagari(token: str) -> bool:
    """A well-formed Devanagari word: starts with a letter, no stacked vowel signs. Proper names pass; mojibake does not."""
    return len(token) >= 2 and bool(_DEVANAGARI_START.match(token)) and not _DOUBLE_SIGN.search(token)


def word_share(text: str) -> float | None:
    """Share of words that are English or Hindi words.

    Counted: English words, and Devanagari words. A Devanagari word counts as known when it is in the Hindi list or is
    well-formed Unicode (so names do not hurt a good text layer). Not counted: capitalised words that are not sentence
    starts and acronyms (names, places, FIR, IPC), single letters and numbers.

    Args:
        text: page text

    Returns:
        The share from 0 to 1, or None when the text has no countable words.
    """
    known = total = 0
    sentence_start = True
    for m in re.finditer(r"[A-Za-z]+(?:'[a-z]+)?|[ऀ-ॣ०-ॿ]+|[.!?:]", text):
        token = m.group(0)
        if token in ".!?:":
            sentence_start = True
            continue
        at_start, sentence_start = sentence_start, False
        if _HI_TOKEN.fullmatch(token):
            total += 1
            known += token in hindi_words() or _valid_devanagari(token)
            continue
        if len(token) < 2 or token.isupper():
            continue
        if token[0].isupper() and not at_start and token[1:].islower() and not _known_english(token):
            continue  # a name or place
        total += 1
        known += _known_english(token)
    return known / total if total else None
