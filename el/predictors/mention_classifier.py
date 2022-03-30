# -*- coding: utf-8 -*-
from allennlp.predictors.predictor import Predictor


@Predictor.register("mention_classifier")
class MentionClassifierPredictor(Predictor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._dataset_reader._negative_sampling_rate = 1.0
        self._dataset_reader._use_span_labels = False

    def process_predictions(self, prediction, docs):
        for mention_start, mention_end, mention_label in prediction["predicted_spans"]:
            docs[prediction["doc_id"]]["sentences"][prediction["sentence_index"]][
                "mentions"
            ].append(
                {
                    "start": mention_start,
                    "end": mention_end,
                    "label": mention_label,
                    "references": {},
                }
            )
