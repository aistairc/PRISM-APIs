# -*- coding: utf-8 -*-
import logging
import random
from collections import defaultdict
from typing import Any, Dict, Iterator, List, Optional

from allennlp.data.dataset_readers.dataset_reader import DatasetReader
from allennlp.data.dataset_readers.dataset_utils import enumerate_spans
from allennlp.data.fields import ListField, MetadataField, SpanField, TextField
from allennlp.data.instance import Instance
from allennlp.data.token_indexers import SingleIdTokenIndexer, TokenIndexer
from allennlp.data.tokenizers import Token
from el.data.fields.multilabel_field import MultiLabelField
from overrides import overrides

# from el.tools.standoff_reader import filter_mentions

logger = logging.getLogger(__name__)


@DatasetReader.register("mention_classifier")
class MentionClassifierReader(DatasetReader):
    def __init__(
        self,
        max_span_width: int,
        negative_sampling_rate: float = 1.0,
        use_detection: Optional[bool] = False,
        stripped_labels: Optional[List[str]] = [],
        token_indexers: Optional[Dict[str, TokenIndexer]] = None,
        lazy: Optional[bool] = False,
    ) -> None:
        super().__init__(lazy)

        self._max_span_width = max_span_width
        self._negative_sampling_rate = negative_sampling_rate if lazy else 1.0
        self._use_detection = use_detection
        self._stripped_labels = stripped_labels
        self._use_span_labels = True
        self._token_indexers = token_indexers or {"tokens": SingleIdTokenIndexer()}

    @overrides
    def _read(self, docs) -> Iterator[Instance]:
        # docs = filter_mentions(docs, stripped_labels=self._stripped_labels)

        for doc_id, doc in docs.items():
            for sentence_index, sentence in enumerate(doc["sentences"]):
                instance = self.text_to_instance(
                    tokens=sentence["tokens"],
                    doc_id=doc_id,
                    sentence_index=sentence_index,
                    gold_mentions=[],
                )

                if instance:
                    yield instance

    @overrides
    def text_to_instance(
        self,
        tokens: List[str],
        doc_id: str,
        sentence_index: int,
        gold_mentions: List[Dict[str, Any]],
    ) -> Instance:

        text_field = TextField(
            [Token(token) for token in tokens], token_indexers=self._token_indexers
        )

        gold_spans = []
        gold_span_labels = defaultdict(set)

        for mention in gold_mentions:
            if self._use_detection:
                mention["label"] = "ENTITY"

            gold_spans.append((mention["start"], mention["end"], mention["label"]))
            gold_span_labels[mention["start"], mention["end"]].add(mention["label"])

        spans = []
        span_labels = []

        for span in enumerate_spans(tokens, max_span_width=self._max_span_width):
            if (
                self._negative_sampling_rate < 1.0
                and span not in gold_span_labels
                and random.random() >= self._negative_sampling_rate
            ):
                continue

            spans.append(SpanField(*span, text_field))
            span_labels.append(MultiLabelField(gold_span_labels.get(span, [])))

        if spans:
            span_fields = ListField(spans)

            metadata_field = MetadataField(
                {
                    "doc_id": doc_id,
                    "sentence_index": sentence_index,
                    "gold_spans": gold_spans,
                }
            )

            fields = {
                "tokens": text_field,
                "spans": span_fields,
                "metadata": metadata_field,
            }

            if self._use_span_labels:
                fields["span_labels"] = ListField(span_labels)

            return Instance(fields)
