# -*- coding: utf-8 -*-
import string
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


@DatasetReader.register("dual_encoder")
class DualEncoderReader(DatasetReaderWithConceptCache):
    def __init__(
        self,
        umls_kb_file: str,
        umls_kb_cache_file: Optional[str] = None,
        context_window_size: int = 5,
        max_sequence_length: int = 32,
        stripped_labels: List[str] = [],
        export_umls_concept_embeddings: bool = False,
        token_indexers: Optional[Dict[str, TokenIndexer]] = None,
        lazy: bool = False,
    ) -> None:
        super().__init__(lazy=lazy)

        assert (
            ~max_sequence_length & 1
        ), "`max_sequence_length` must be an even positive integer"

        self._umls_kb_file = umls_kb_file
        self._umls_kb_cache_file = umls_kb_cache_file
        self._context_window_size = context_window_size
        self._max_sequence_length = max_sequence_length
        self._stripped_labels = stripped_labels

        self._token_splitter = BertBasicWordSplitter(do_lower_case=False)
        self._token_indexers = token_indexers or {"tokens": SingleIdTokenIndexer()}

        self._concepts = {}

        self._export_umls_concept_embeddings = export_umls_concept_embeddings
        self._prediction_mode = export_umls_concept_embeddings

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

    def process_tokens(self, tokens: List[str]) -> List[str]:
        return tuple(
            token.lower() for token in tokens if token not in string.punctuation
        )

    def tokenize_sentence(self, sentence: str) -> List[str]:
        return self._token_splitter.basic_tokenizer.tokenize(sentence)

    @overrides
    def _read(self, docs) -> Iterator[Instance]:
        self.load_concepts()

        if not self._export_umls_concept_embeddings:
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

                        if self._prediction_mode:
                            all_mentions.append(
                                {
                                    "doc_id": doc_id,
                                    "mention_id": mention["id"],
                                    "span": mention_span,
                                    "left_context": mention_left_context,
                                    "right_context": mention_right_context,
                                    "context": mention_context,
                                }
                            )
                        else:
                            for _, concept_id in mention["references"]:
                                if concept_id in self._concepts:
                                    all_mentions.append(
                                        {
                                            "doc_id": doc_id,
                                            "mention_id": mention["id"],
                                            "span": mention_span,
                                            "left_context": mention_left_context,
                                            "right_context": mention_right_context,
                                            "context": mention_context,
                                            "concept_id": concept_id,
                                        }
                                    )
                                else:
                                    logger.warning(
                                        "Removed out-of-KB concept `{}` from mention `{}` in `{}`",
                                        concept_id,
                                        mention["id"],
                                        doc_id,
                                    )

        if self._export_umls_concept_embeddings:
            for concept in self._concepts.values():
                yield self.text_to_instance(
                    concept={
                        "id": concept["id"],
                        "canonical_name": concept["canonical_name"],
                        "definition": concept["definition"],
                        "alias_index": -1,
                        "semantic_types": concept["semantic_types"],
                    }
                )

                for alias_index, alias_name in enumerate(concept["aliases"]):
                    yield self.text_to_instance(
                        concept={
                            "id": concept["id"],
                            "canonical_name": alias_name,
                            "definition": concept["definition"],
                            "alias_index": alias_index,
                            "semantic_types": concept["semantic_types"],
                        }
                    )
        else:
            for mention in all_mentions:
                if self._prediction_mode:
                    yield self.text_to_instance(mention=mention)
                else:
                    concept = self._concepts[mention["concept_id"]]

                    yield self.text_to_instance(
                        mention=mention,
                        concept={
                            "id": concept["id"],
                            "canonical_name": concept["canonical_name"],
                            "definition": concept["definition"],
                            "alias_index": -1,
                            "semantic_types": concept["semantic_types"],
                        },
                    )

                    for alias_index, alias_name in enumerate(concept["aliases"]):
                        yield self.text_to_instance(
                            mention=mention,
                            concept={
                                "id": concept["id"],
                                "canonical_name": alias_name,
                                "definition": concept["definition"],
                                "alias_index": alias_index,
                                "semantic_types": concept["semantic_types"],
                            },
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
        id_field = LabelField(int("42" + concept["id"][1:]), skip_indexing=True)

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
            namespace + "_id": id_field,
            namespace + "_canonical_name": canonical_name_field,
            namespace + "_definition": definition_field,
            namespace + "_semantic_types": semantic_types_field,
        }

    @overrides
    def text_to_instance(
        self,
        mention: Optional[Dict[str, Any]] = None,
        concept: Optional[Dict[str, Any]] = None,
    ) -> Instance:
        fields = {"metadata": MetadataField({"mention": mention, "concept": concept})}

        if mention:
            fields.update(self.get_mention_fields(mention, namespace="mention"))

        if concept:
            fields.update(self.get_concept_fields(concept, namespace="concept"))

        return Instance(fields)
