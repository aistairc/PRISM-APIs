# -*- coding: utf-8 -*-
import random
from typing import Any, Dict, Iterator, List, Optional

from allennlp.data.dataset_readers.dataset_reader import DatasetReader
from allennlp.data.fields import Field, ListField, MetadataField, TextField
from allennlp.data.instance import Instance
from allennlp.data.token_indexers import SingleIdTokenIndexer, TokenIndexer
from allennlp.data.tokenizers import Token
from allennlp.data.tokenizers.word_splitter import BertBasicWordSplitter
from el.data.fields.label_field import LabelField
from el.data.readers.dataset_reader_with_concept_cache import (
    DatasetReaderWithConceptCache,
)
from loguru import logger
from overrides import overrides
from tqdm import tqdm

# from el.tools.standoff_reader import filter_mentions


@DatasetReader.register("entity_ranking")
class EntityRankingReader(DatasetReaderWithConceptCache):
    def __init__(
        self,
        umls_kb_file: str,
        umls_kb_cache_file: Optional[str] = None,
        k_candidates: int = 50,
        context_window_size: int = 5,
        max_sequence_length: int = 32,
        stripped_labels: List[str] = [],
        token_indexers: Optional[Dict[str, TokenIndexer]] = None,
        lazy: bool = False,
    ) -> None:
        super().__init__(lazy=lazy)

        assert lazy, "`lazy` must be enabled for negative sampling every epoch"

        assert k_candidates > 1, "`k_candidates` must be greater than 1"

        assert (
            ~max_sequence_length & 1
        ), "`max_sequence_length` must be an even positive integer"

        self._umls_kb_file = umls_kb_file
        self._umls_kb_cache_file = umls_kb_cache_file
        self._k_candidates = k_candidates
        self._context_window_size = context_window_size
        self._max_sequence_length = max_sequence_length
        self._stripped_labels = stripped_labels

        self._token_splitter = BertBasicWordSplitter(do_lower_case=False)
        self._token_indexers = token_indexers or {"tokens": SingleIdTokenIndexer()}

        self._concepts = {}
        self._concept_ids = None

        self._prediction_mode = False

    def truncate_with_maximal_context(self, pos: int, tokens: List[str]) -> List[str]:
        assert 0 <= pos < len(tokens)

        half_max_sequence_length = self._max_sequence_length // 2

        left_pos = max(
            max(pos - half_max_sequence_length, 0)
            - max(pos + half_max_sequence_length + 1 - len(tokens), 0),
            0,
        )

        tokens = tokens[left_pos : left_pos + self._max_sequence_length + 1]

        # Make sure the algorithm is correct
        assert (
            0 < len(tokens) <= self._max_sequence_length + 1
            and tokens[pos - left_pos] == self.SPECIAL_MENTION_TOKEN
        )

        return tokens

    @overrides
    def _read(self, docs: str) -> Iterator[Instance]:
        self.load_concepts()

        if True:
            logger.info("Preprocessing the mentions")

            all_mentions = []

            # docs = filter_mentions(docs=docs, stripped_labels=self._stripped_labels)

            for doc_id, doc in tqdm(docs.items(), desc="Processing corpus"):
                for sentence in doc["sentences"]:
                    for mention in sentence["mentions"]:
                        mention_span = self.process_tokens(
                            sentence["tokens"][mention["start"] : mention["end"] + 1]
                        )

                        if not mention_span:
                            logger.warning(
                                "Removed invalid mention `{}` in `{}`",
                                mention["id"],
                                doc_id,
                            )

                            continue

                        mention_left_context = sentence["tokens"][: mention["start"]]

                        mention_right_context = sentence["tokens"][mention["end"] + 1 :]

                        mention_context = (
                            mention_left_context
                            + [self.SPECIAL_MENTION_TOKEN]
                            + mention_right_context
                        )

                        mention_context = self.process_tokens(
                            self.truncate_with_maximal_context(
                                pos=mention["start"], tokens=mention_context
                            )
                        )

                        assert mention_context

                        mention_left_context = self.process_tokens(
                            mention_left_context[-self._context_window_size :]
                        )

                        if not mention_left_context:
                            mention_left_context = [self.SPECIAL_NULL_TOKEN]

                        assert mention_left_context

                        mention_right_context = self.process_tokens(
                            mention_right_context[: self._context_window_size]
                        )

                        if not mention_right_context:
                            mention_right_context = [self.SPECIAL_NULL_TOKEN]

                        assert mention_right_context

                        predicted_concept_ids = set()
                        gold_concept_ids = set()

                        for (concept_source, concept_id), concept_similarity in mention[
                            "references"
                        ].items():
                            concept_id, alias_index, *_ = map(
                                str.strip, (concept_id + "/-1").split("/")
                            )

                            if concept_id in self._concepts:
                                if concept_source == "PRED":
                                    predicted_concept_ids.add(
                                        (
                                            concept_id,
                                            int(alias_index),
                                            float(concept_similarity),
                                        )
                                    )
                                else:
                                    gold_concept_ids.add(concept_id)
                            else:
                                logger.warning(
                                    "Removed out-of-KB concept `{}:{}` from mention `{}` in `{}`",
                                    concept_source,
                                    concept_id,
                                    mention["id"],
                                    doc_id,
                                )

                        if self._prediction_mode:
                            gold_concept_ids.clear()

                        predicted_concept_ids = {
                            (concept_id, alias_index, concept_similarity)
                            for concept_id, alias_index, concept_similarity in predicted_concept_ids
                            if concept_id not in gold_concept_ids
                        }

                        predicted_concept_ids = sorted(
                            predicted_concept_ids, key=lambda v: v[-1], reverse=True
                        )

                        all_mentions.append(
                            {
                                "doc_id": doc_id,
                                "mention_id": mention["id"],
                                "span": mention_span,
                                "left_context": mention_left_context,
                                "right_context": mention_right_context,
                                "context": mention_context,
                                "gold_concept_ids": gold_concept_ids,
                                "predicted_concept_ids": predicted_concept_ids,
                            }
                        )

        def generate_candidate_instances(candidates):
            candidate_instances = []

            for concept_id, alias_index in candidates:
                concept = self._concepts[concept_id]

                candidate_instances.append(
                    {
                        "id": concept["id"],
                        "canonical_name": (
                            [concept["canonical_name"]] + concept["aliases"]
                        )[
                            alias_index + 1
                        ],  # Start from -1
                        "alias_index": alias_index,
                        "definition": concept["definition"],
                        "semantic_types": concept["semantic_types"],
                    }
                )

            return candidate_instances

        for mention in all_mentions:
            mention_instance = {
                "doc_id": mention["doc_id"],
                "mention_id": mention["mention_id"],
                "span": mention["span"],
                "left_context": mention["left_context"],
                "right_context": mention["right_context"],
                "context": mention["context"],
            }

            predicted_candidates = []
            predicted_candidate_ids = set()

            for concept_id, alias_index, _ in mention["predicted_concept_ids"][
                : self._k_candidates
            ]:
                predicted_candidates.append((concept_id, alias_index))
                predicted_candidate_ids.add(concept_id)

            if self._prediction_mode:
                # Padding
                if (
                    predicted_candidates
                    and len(predicted_candidates) < self._k_candidates
                ):
                    predicted_candidates += [predicted_candidates[-1]] * (
                        self._k_candidates - len(predicted_candidates)
                    )

                if predicted_candidates:
                    yield self.text_to_instance(
                        mention=mention_instance,
                        candidates=generate_candidate_instances(predicted_candidates),
                    )
            else:
                for gold_concept_id in mention["gold_concept_ids"]:
                    gold_concept = self._concepts[gold_concept_id]

                    gold_alias_index = random.choice(
                        range(-1, len(gold_concept["aliases"]))
                    )

                    candidates = (
                        [(gold_concept_id, gold_alias_index)] + predicted_candidates
                    )[: self._k_candidates]

                    candidate_ids = {gold_concept_id} | predicted_candidate_ids

                    while len(candidates) < self._k_candidates:
                        while True:
                            candidate_id = random.choice(self._concept_ids)

                            if candidate_id not in candidate_ids:
                                break

                        candidates.append(
                            (
                                candidate_id,
                                random.choice(
                                    range(
                                        -1,
                                        len(self._concepts[candidate_id]["aliases"]),
                                    )
                                ),
                            )
                        )

                        candidate_ids.add(candidate_id)

                    yield self.text_to_instance(
                        mention=mention_instance,
                        candidates=generate_candidate_instances(candidates),
                    )

    def get_mention_fields(
        self, mention: Dict[str, Any], namespace: str = "mention"
    ) -> Dict[str, Field]:

        span_field = TextField(
            [Token(token) for token in mention["span"]],
            token_indexers=self._token_indexers,
        )

        left_context_field = TextField(
            [Token(token) for token in mention["left_context"]],
            token_indexers=self._token_indexers,
        )

        right_context_field = TextField(
            [Token(token) for token in mention["right_context"]],
            token_indexers=self._token_indexers,
        )

        context_field = TextField(
            [Token(token) for token in mention["context"]],
            token_indexers=self._token_indexers,
        )

        return {
            namespace + "_span": span_field,
            namespace + "_left_context": left_context_field,
            namespace + "_right_context": right_context_field,
            namespace + "_context": context_field,
        }

    def get_concept_fields(
        self, concept: Dict[str, Any], namespace: str = "concept"
    ) -> Dict[str, Field]:

        canonical_name_field = TextField(
            [Token(token) for token in concept["canonical_name"]],
            token_indexers=self._token_indexers,
        )

        definition_field = TextField(
            [Token(token) for token in concept["definition"]],
            token_indexers=self._token_indexers,
        )

        semantic_types_field = ListField(
            [
                LabelField(
                    semantic_type, label_namespace="semantic_types", padding_value=0
                )
                for semantic_type in concept["semantic_types"]
            ]
        )

        return {
            namespace + "_canonical_name": canonical_name_field,
            namespace + "_definition": definition_field,
            namespace + "_semantic_types": semantic_types_field,
        }

    @overrides
    def text_to_instance(
        self,
        mention: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> Instance:

        assert len(candidates) == self._k_candidates, "Found an invalid candidate list"

        fields = {
            "metadata": MetadataField({"mention": mention, "candidates": candidates})
        }

        fields.update(self.get_mention_fields(mention, namespace="mention"))

        for candidate_index, candidate in enumerate(candidates):
            fields.update(
                self.get_concept_fields(
                    candidate, namespace="candidate_" + str(candidate_index)
                )
            )

        return Instance(fields)
