"""
MorphologyStage — adds lemma, POS, and morphological features to tokens.

Runs Stanza with ``processors="tokenize,pos,lemma"`` (plus ``mwt`` for Latin)
on text that has already been tokenised by ``TEIParser``.  The
``tokenize_pretokenized=True`` flag tells Stanza to skip re-tokenisation and
only run the downstream annotators.

Token dicts are annotated in-place with three new optional keys:

``lemma``
    The dictionary form of the token.
``pos``
    Universal Dependencies POS tag (e.g. ``"NOUN"``, ``"VERB"``).
``xpos``
    Language-specific POS tag.
``morphology``
    A flat ``dict[str, str]`` of Universal Dependencies feature–value pairs,
    e.g. ``{"Case": "Nom", "Gender": "Masc", "Number": "Sing"}``.

Latin MWT (multi-word token) note
----------------------------------
The Latin Perseus Stanza model includes multi-word token expansion, which
means one surface token may expand into several syntactic words.  When the
Stanza word count for a sentence differs from the token count in the dict,
``_align_tokens`` falls back to text-based matching so that the annotation
is never silently misaligned.
"""

import logging
from typing import ClassVar

import stanza

logger = logging.getLogger(__name__)


def _parse_feats(feats_str: str) -> dict[str, str]:
    """Parse ``"Case=Nom|Gender=Masc|Number=Sing"`` into a dict."""
    if not feats_str or feats_str == "_":
        return {}
    return dict(pair.split("=", 1) for pair in feats_str.split("|") if "=" in pair)


def _align_tokens(
    token_dicts: list[dict], stanza_words: list
) -> list[tuple[dict, object]]:
    """
    Align ``token_dicts`` with ``stanza_words``.

    When counts match, alignment is positional (fast path).
    When they differ (Latin MWT expansion), fall back to matching by the
    surface text of the first word that starts with the token text.
    Unmatched token dicts are left unannotated.
    """
    if len(token_dicts) == len(stanza_words):
        return list(zip(token_dicts, stanza_words))

    pairs: list[tuple[dict, object]] = []
    word_iter = iter(stanza_words)
    for tok in token_dicts:
        matched = None
        for word in word_iter:
            if word.text and tok["text"].startswith(word.text):
                matched = word
                break
        pairs.append((tok, matched))
    return pairs


class MorphologyStage:
    """
    Pipeline stage that adds morphological annotations to all tokens.

    Parameters
    ----------
    language:
        Override the document language.  When ``None`` (the default), the
        language is read from ``document["language"]`` at processing time.
    model_dir:
        Path to the directory where Stanza models are stored.
    package:
        Stanza package name.  Defaults to ``"perseus"`` (the package
        trained on the Perseus Digital Library data).
    """

    _pipelines: ClassVar[dict[str, stanza.Pipeline]] = {}

    def __init__(
        self,
        language: str | None = None,
        model_dir: str = "./stanza_models",
        package: str = "perseus",
    ) -> None:
        self.language = language
        self.model_dir = model_dir
        self.package = package

    # ------------------------------------------------------------------
    # DocumentStage protocol
    # ------------------------------------------------------------------

    def process(self, document: dict) -> dict:
        lang = self._resolve_language(document)
        nlp = self._get_pipeline(lang)

        for textpart in document.get("textparts", []):
            tokens = textpart.get("tokens", [])
            if tokens:
                self._annotate_tokens(nlp, tokens)

        return document

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_language(self, document: dict) -> str:
        raw = self.language or document.get("language") or "grc"
        # Normalise Latin variants
        return "la" if raw in ("la", "lat") else raw

    def _get_pipeline(self, language: str) -> stanza.Pipeline:
        key = f"{language}:{self.package}"
        if key not in MorphologyStage._pipelines:
            processors = "tokenize,pos,lemma"
            if language == "la":
                # The Latin Perseus model includes MWT expansion
                processors = "tokenize,mwt,pos,lemma"
            MorphologyStage._pipelines[key] = stanza.Pipeline(
                language,
                processors=processors,
                package=self.package,
                model_dir=self.model_dir,
                download_method=stanza.DownloadMethod.REUSE_RESOURCES,
                tokenize_pretokenized=True,
            )
            logger.info(f"Loaded Stanza morphology pipeline for '{language}'")
        return MorphologyStage._pipelines[key]

    def _annotate_tokens(self, nlp: stanza.Pipeline, tokens: list[dict]) -> None:
        # Stanza expects a list[list[str]] when tokenize_pretokenized=True
        token_texts = [[t["text"] for t in tokens]]
        try:
            doc = nlp(token_texts)
        except Exception:
            logger.exception("Stanza annotation failed; skipping textpart")
            return

        stanza_words = [
            word for sentence in doc.sentences for word in sentence.words
        ]

        for tok_dict, stanza_word in _align_tokens(tokens, stanza_words):
            if stanza_word is None:
                continue
            tok_dict["lemma"] = stanza_word.lemma or tok_dict["text"]
            tok_dict["pos"] = stanza_word.upos or ""
            tok_dict["xpos"] = stanza_word.xpos or ""
            tok_dict["morphology"] = _parse_feats(stanza_word.feats or "")
