import os
import string
from typing import List

from allennlp.data.dataset_readers.dataset_reader import DatasetReader
from el.common import file_utils
from loguru import logger
from tqdm import tqdm

internal_concepts_cache = {}


class DatasetReaderWithConceptCache(DatasetReader):
    SPECIAL_MENTION_TOKEN = "<mention>"
    SPECIAL_NULL_TOKEN = "<null>"

    def process_tokens(self, tokens: List[str]) -> List[str]:
        return tuple(
            token.lower() for token in tokens if token not in string.punctuation
        )

    def tokenize_sentence(self, sentence: str) -> List[str]:
        return self._token_splitter.basic_tokenizer.tokenize(sentence)

    def load_concepts(self) -> None:
        if self._concepts:
            return

        if self._umls_kb_file in internal_concepts_cache:
            self._concepts, self._concept_ids = internal_concepts_cache[
                self._umls_kb_file
            ]
            return

        needs_init = True
        cache_method = None
        self._concepts = {}

        if self._umls_kb_cache_file:
            filestem, cache_method = os.path.splitext(self._umls_kb_cache_file)
            gzipped = cache_method == ".gz"
            if gzipped:
                __, cache_method = os.path.splitext(filestem)

            assert cache_method in [
                ".json",
                ".sqlite",
            ], "umls_kb_cache_file must be None, .json, .json.gz or .sqlite, but is {}".format(
                self._umls_kb_cache_file
            )

            if os.path.exists(self._umls_kb_cache_file):
                needs_init = False

            if cache_method == ".sqlite":
                from sqlitedict import SqliteDict

                flag = "n" if needs_init else "r"

                self._concepts = SqliteDict(
                    filename=self._umls_kb_cache_file,
                    flag=flag,
                )

            elif cache_method == ".json":
                import json

                if gzipped:
                    import gzip

                    open_func = gzip.open
                else:
                    open_func = open

                if not needs_init:
                    logger.info(
                        "Loading UMLS knowledge base from cache `{}`",
                        self._umls_kb_cache_file,
                    )

                    with open_func(self._umls_kb_cache_file, "rt") as r:
                        self._concepts = json.load(r)

        if needs_init:
            logger.info("Preprocessing UMLS knowledge base `{}`", self._umls_kb_file)

            self._populate_concepts()

            if cache_method:
                logger.info(
                    "Saving UMLS knowledge base to cache `{}`", self._umls_kb_cache_file
                )

                if cache_method == ".sqlite":
                    self._concepts.commit()

                elif cache_method == ".json":
                    with open_func(self._umls_kb_cache_file, "wt") as w:
                        json.dump(self._concepts, w)

        self._concept_ids = list(self._concepts.keys())
        internal_concepts_cache[self._umls_kb_file] = (
            self._concepts,
            self._concept_ids,
        )

    def _populate_concepts(self):
        for concept in tqdm(
            file_utils.read_json_lines(self._umls_kb_file), desc="Processing KB"
        ):
            concept_id = concept["id"]

            concept_canonical_name = self.process_tokens(
                self.tokenize_sentence(concept["name"])
            )

            assert concept_canonical_name

            concept_definition = self.process_tokens(
                self.tokenize_sentence(concept["definition"])
            )[
                : self._max_sequence_length + 1
            ]  # Same length as mention context

            if not concept_definition:
                concept_definition = [self.SPECIAL_NULL_TOKEN]

            concept_aliases = {
                self.process_tokens(self.tokenize_sentence(alias_name))
                for alias_name in concept["aliases"]
            } - {concept_canonical_name}

            concept_aliases = sorted(filter(None, concept_aliases))

            concept_semantic_types = sorted(concept["types"])

            self._concepts[concept_id] = {
                "id": concept_id,
                "canonical_name": concept_canonical_name,
                "definition": concept_definition,
                "aliases": concept_aliases,
                "semantic_types": concept_semantic_types,
            }
