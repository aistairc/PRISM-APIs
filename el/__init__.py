# -*- coding: utf-8 -*-
from allennlp.predictors.predictor import DEFAULT_PREDICTORS

from el.data.readers.dual_encoder import DualEncoderReader
from el.data.readers.entity_ranking import EntityRankingReader
from el.data.readers.mention_classifier import MentionClassifierReader
from el.models.dual_encoder import DualEncoder
from el.models.entity_ranking import EntityRanking
from el.models.mention_classifier import MentionClassifier
from el.nn.activations import SmoothGelu
from el.predictors.dual_encoder import DualEncoderPredictor
from el.predictors.entity_ranking import EntityRankingPredictor
from el.predictors.mention_classifier import MentionClassifierPredictor

DEFAULT_PREDICTORS.update(
    {
        "dual_encoder": "dual_encoder",
        "entity_ranking": "entity_ranking",
        "mention_classifier": "mention_classifier",
    }
)
