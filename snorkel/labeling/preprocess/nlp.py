from typing import List

import spacy

from snorkel.types import FieldMap

from .core import Preprocessor

DEFAULT_DISABLE = ["parser", "ner"]
EN_CORE_WEB_SM = "en_core_web_sm"


class SpacyPreprocessor(Preprocessor):
    """Preprocessor that parses input text via a SpaCy model.

    Parameters
    ----------
    text_field
        Name of data point text field to input
    doc_field
        Name of data point field to output parsed document to
    language
        SpaCy model to load, by default EN_CORE_WEB_SM.
        See https://spacy.io/usage/models#usage
    disable
        List of pipeline components to disable, by default DEFAULT_DISABLE.
        See https://spacy.io/usage/processing-pipelines#disabling
    """

    def __init__(
        self,
        text_field: str,
        doc_field: str,
        language: str = EN_CORE_WEB_SM,
        disable: List[str] = DEFAULT_DISABLE,
    ) -> None:
        super().__init__(dict(text=text_field), dict(doc=doc_field))
        self._nlp = spacy.load(language, disable=disable)

    def run(self, text: str) -> FieldMap:  # type: ignore
        """Run the SpaCy model on input text.

        Parameters
        ----------
        text
            Text of document to parse

        Returns
        -------
        FieldMap
            Mapping containing parsed document
        """
        return dict(doc=self._nlp(text))
