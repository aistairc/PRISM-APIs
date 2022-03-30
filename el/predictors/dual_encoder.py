# -*- coding: utf-8 -*-
import json
import os

import numpy as np
from allennlp.predictors.predictor import Predictor
from el.common import file_utils


@Predictor.register("dual_encoder")
class DualEncoderPredictor(Predictor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._dataset_reader._prediction_mode = True
        self._model._prediction_mode = True

        self._export_umls_concept_embeddings = (
            self._dataset_reader._export_umls_concept_embeddings
        )

        self._embedding_dimension = (
            self._model._concept_encoder_feedforward.get_output_dim()
        )

        self._do_preprocessing = True

    def preprocess_predictions(self):
        file_utils.make_dirs(self._output_file)

    def process_predictions(self, prediction):
        if self._do_preprocessing:
            self._do_preprocessing = False

            if self._export_umls_concept_embeddings:
                num_concepts = sum(
                    1 + len(concept["aliases"])
                    for concept in self._dataset_reader._concepts.values()
                )

                self._concepts = {
                    "ids": [],
                    "size": (num_concepts, self._embedding_dimension),
                }

                self._concept_embeddings = np.memmap(
                    filename=os.path.join(self._output_file, "concept_embeddings.npy"),
                    dtype=np.float32,
                    mode="w+",
                    shape=self._concepts["size"],
                )
            else:
                num_mentions = len(self._dataset_reader._mentions[self._input_file])

                self._mentions = {
                    "ids": [],
                    "size": (num_mentions, self._embedding_dimension),
                }

                self._mention_embeddings = np.memmap(
                    filename=os.path.join(self._output_file, "mention_embeddings.npy"),
                    dtype=np.float32,
                    mode="w+",
                    shape=self._mentions["size"],
                )

        prediction = json.loads(prediction)

        metadata = prediction["metadata"]

        if self._export_umls_concept_embeddings:
            concept = metadata["concept"]

            self._concept_embeddings[len(self._concepts["ids"])] = prediction[
                "concept_embeddings"
            ]

            self._concepts["ids"].append((concept["id"], concept["alias_index"]))
        else:
            mention = metadata["mention"]

            self._mention_embeddings[len(self._mentions["ids"])] = prediction[
                "mention_embeddings"
            ]

            self._mentions["ids"].append((mention["doc_id"], mention["mention_id"]))

    def finalize_predictions(self):
        if self._export_umls_concept_embeddings:
            assert len(self._concepts["ids"]) == len(self._concept_embeddings)

            del self._concept_embeddings

            file_utils.write_json(
                self._concepts, os.path.join(self._output_file, "concepts.json")
            )
        else:
            assert len(self._mentions["ids"]) == len(self._mention_embeddings)

            del self._mention_embeddings

            file_utils.write_json(
                self._mentions, os.path.join(self._output_file, "mentions.json")
            )
