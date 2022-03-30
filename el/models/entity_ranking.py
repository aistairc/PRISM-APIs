# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from allennlp.data import Vocabulary
from allennlp.models.model import Model
from allennlp.modules import Embedding, FeedForward, Seq2VecEncoder, TextFieldEmbedder
from allennlp.nn import InitializerApplicator, RegularizerApplicator, util
from overrides import overrides

# from el.training.metrics import Auc, Average

logger = logging.getLogger(__name__)


@Model.register("entity_ranking")
class EntityRanking(Model):
    def __init__(
        self,
        vocab: Vocabulary,
        text_field_embedder: TextFieldEmbedder,
        text_field_encoder: Seq2VecEncoder,
        text_field_feedforward: FeedForward,
        mention_context_feedforward: FeedForward,
        mention_encoder_feedforward: FeedForward,
        sparse_embedder: Embedding,
        sparse_encoder: Seq2VecEncoder,
        sparse_feedforward: FeedForward,
        concept_context_feedforward: FeedForward,
        concept_encoder_feedforward: FeedForward,
        threshold: float = 0.5,
        dropout: float = 0.0,
        initializer: InitializerApplicator = InitializerApplicator(),
        regularizer: Optional[RegularizerApplicator] = None,
    ) -> None:
        super().__init__(vocab, regularizer)

        # Text encoder
        self._text_field_embedder = text_field_embedder
        self._text_field_encoder = text_field_encoder
        self._text_field_feedforward = text_field_feedforward

        # Mentions
        self._mention_context_feedforward = mention_context_feedforward
        self._mention_encoder_feedforward = mention_encoder_feedforward

        # Concepts
        self._sparse_embedder = sparse_embedder
        self._sparse_encoder = sparse_encoder
        self._sparse_feedforward = sparse_feedforward

        self._concept_context_feedforward = concept_context_feedforward
        self._concept_encoder_feedforward = concept_encoder_feedforward

        self._classifier = nn.Linear(in_features=1, out_features=1, bias=False)

        # Bias is needed for the logistic loss, as the softmax function is invariant to translation
        # f(x) = Wx + b
        # W must be a positive value to make the cosine similarity correct
        self._multiplier = nn.Linear(in_features=1, out_features=1, bias=True)

        self._threshold = threshold

        self._dropout = nn.Dropout(p=dropout)

        # Metric
        # self._auc_metric = Auc(positive_label=1)
        # self._accuracy_metric = Average()

        # For prediction (value modified from predictor)
        self._prediction_mode = False

        initializer(self)

    def get_text_embeddings(self, field: Dict[str, torch.LongTensor]):
        field_mask = util.get_text_field_mask(field)

        field_embeddings = self._text_field_embedder(field)
        field_embeddings = self._text_field_encoder(field_embeddings, mask=field_mask)
        field_embeddings = self._text_field_feedforward(field_embeddings)

        return field_embeddings

    def get_sparse_embeddings(self, field: torch.LongTensor):
        field_embeddings = self._sparse_embedder(field)
        field_embeddings = self._sparse_encoder(field_embeddings, mask=field > 0)
        field_embeddings = self._sparse_feedforward(field_embeddings)

        return field_embeddings

    def get_mention_embeddings(
        self,
        mention_span: Dict[str, torch.LongTensor],
        mention_left_context: Dict[str, torch.LongTensor],
        mention_right_context: Dict[str, torch.LongTensor],
        mention_context: Dict[str, torch.LongTensor],
    ):
        mention_span_embeddings = self.get_text_embeddings(mention_span)
        mention_left_context_embeddings = self.get_text_embeddings(mention_left_context)
        mention_right_context_embeddings = self.get_text_embeddings(
            mention_right_context
        )
        mention_context_embeddings = self.get_text_embeddings(mention_context)

        combined_mention_context_embeddings = torch.cat(
            [
                mention_left_context_embeddings,
                mention_right_context_embeddings,
                mention_context_embeddings,
            ],
            dim=-1,
        )

        combined_mention_context_embeddings = self._dropout(
            combined_mention_context_embeddings
        )

        combined_mention_context_embeddings = self._mention_context_feedforward(
            combined_mention_context_embeddings
        )

        mention_embeddings = torch.cat(
            [mention_span_embeddings, combined_mention_context_embeddings], dim=-1
        )

        mention_embeddings = self._dropout(mention_embeddings)

        mention_embeddings = self._mention_encoder_feedforward(mention_embeddings)

        return mention_embeddings

    def get_concept_embeddings(
        self,
        concept_canonical_name: Dict[str, torch.LongTensor],
        concept_definition: Dict[str, torch.LongTensor],
        concept_semantic_types: torch.LongTensor,
    ):
        concept_canonical_name_embeddings = self.get_text_embeddings(
            concept_canonical_name
        )
        concept_definition_embeddings = self.get_text_embeddings(concept_definition)
        concept_semantic_types_embeddings = self.get_sparse_embeddings(
            concept_semantic_types
        )

        combined_concept_context_embeddings = torch.cat(
            [concept_definition_embeddings, concept_semantic_types_embeddings],
            dim=-1,
        )

        combined_concept_context_embeddings = self._dropout(
            combined_concept_context_embeddings
        )

        combined_concept_context_embeddings = self._concept_context_feedforward(
            combined_concept_context_embeddings
        )

        concept_embeddings = torch.cat(
            [concept_canonical_name_embeddings, combined_concept_context_embeddings],
            dim=-1,
        )

        concept_embeddings = self._dropout(concept_embeddings)

        concept_embeddings = self._concept_encoder_feedforward(concept_embeddings)

        return concept_embeddings

    @overrides
    def forward(self, *args, **kwargs) -> Dict[str, Any]:

        metadata = kwargs["metadata"]

        num_instances = len(metadata)

        num_candidates = len({k for k in kwargs if k.endswith("canonical_name")})

        mention_embedding = self.get_mention_embeddings(
            mention_span=kwargs["mention_span"],
            mention_left_context=kwargs["mention_left_context"],
            mention_right_context=kwargs["mention_right_context"],
            mention_context=kwargs["mention_context"],
        )

        # ce_logits = []
        # bce_logits = []
        raw_logits = []

        for candidate_index in range(num_candidates):
            candidate_embedding = self.get_concept_embeddings(
                concept_canonical_name=kwargs[
                    "candidate_" + str(candidate_index) + "_canonical_name"
                ],
                concept_definition=kwargs[
                    "candidate_" + str(candidate_index) + "_definition"
                ],
                concept_semantic_types=kwargs[
                    "candidate_" + str(candidate_index) + "_semantic_types"
                ],
            )

            cosine_sim = F.cosine_similarity(
                mention_embedding, candidate_embedding, dim=-1, eps=1e-13
            ).unsqueeze(-1)

            # ce_logits.append(self._classifier(cosine_sim))
            # bce_logits.append(self._multiplier(cosine_sim))
            raw_logits.append(cosine_sim)

        # ce_logits = torch.cat(ce_logits, dim=-1)
        # bce_logits = torch.cat(bce_logits, dim=-1)
        raw_logits = torch.cat(raw_logits, dim=-1)

        # Using sigmoid here to find the optimal threshold
        # and allow to link to multiple concepts
        # probabilities = torch.sigmoid(bce_logits.detach().cpu())

        # probabilities = torch.softmax(ce_logits.detach().cpu(), dim=-1)

        probabilities = torch.sigmoid(raw_logits.detach().cpu())

        top_indices = probabilities.argmax(dim=-1)

        is_acceptable_confidence = (probabilities >= self._threshold)[
            range(num_instances), top_indices
        ].tolist()

        outputs = {
            "metadata": metadata,
            "probabilities": probabilities,
            "top_index": top_indices,
            "is_acceptable_confidence": is_acceptable_confidence,
        }

        # if not self._prediction_mode:
        #     gold_labels = torch.tensor(
        #         [[1] + [0] * (num_candidates - 1)] * num_instances
        #     )

        #     self._auc_metric(
        #         predictions=probabilities.flatten().tolist(),
        #         gold_labels=gold_labels.flatten().tolist(),
        #     )

        #     num_matches = (top_indices == 0).sum().item()

        #     self._accuracy_metric(num_corrects=num_matches, num_instances=num_instances)

        #     ce_loss = F.cross_entropy(
        #         input=ce_logits, target=ce_logits.new_zeros(num_instances).long()
        #     )

        #     bce_loss = F.binary_cross_entropy_with_logits(
        #         input=bce_logits, target=bce_logits.new_tensor(gold_labels)
        #     )

        #     outputs["loss"] = (ce_loss + bce_loss) / 2

        return outputs

    # @overrides
    # def get_metrics(self, reset: bool = False) -> Dict[str, float]:
    #     metrics = self._auc_metric.get_metric(reset)

    #     metrics["accuracy"] = self._accuracy_metric.get_metric(reset)

    #     metrics["average"] = (metrics["auc"] + metrics["accuracy"]) / 2

    #     return metrics
