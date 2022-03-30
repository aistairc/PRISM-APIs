# -*- coding: utf-8 -*-
from allennlp.predictors.predictor import Predictor


@Predictor.register("entity_ranking")
class EntityRankingPredictor(Predictor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._dataset_reader._prediction_mode = True
        self._model._prediction_mode = True

    def process_predictions(self, prediction, mention_map):
        mention = prediction["metadata"]["mention"]
        mention = mention_map[mention["doc_id"], mention["mention_id"]]

        mention["references"] = {}

        if prediction["is_acceptable_confidence"]:
            candidate_index = prediction["top_index"]

            candidates = prediction["metadata"]["candidates"]

            mention["references"][
                "PRED", candidates[candidate_index]["id"]
            ] = prediction["probabilities"][candidate_index]
