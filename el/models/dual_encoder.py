# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn

# import torch.nn.functional as F
from allennlp.data import Vocabulary
from allennlp.models.model import Model
from allennlp.modules import Embedding, FeedForward, Seq2VecEncoder, TextFieldEmbedder
from allennlp.modules.matrix_attention import CosineMatrixAttention
from allennlp.nn import InitializerApplicator, RegularizerApplicator, util
from overrides import overrides

# from el.training.metrics import Average

logger = logging.getLogger(__name__)


@Model.register("dual_encoder")
class DualEncoder(Model):
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

        # Objective function
        self._cosine_matrix_attention = CosineMatrixAttention()

        # Bias is needed for the logistic loss, as the softmax function is invariant to translation
        # f(x) = Wx + b
        # W must be a positive value to make the cosine similarity correct
        self._multiplier = nn.Linear(in_features=1, out_features=1, bias=True)

        self._dropout = nn.Dropout(p=dropout)

        # Metric
        # self._recall_metric = Average()

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
    def forward(
        self,
        mention_span: Optional[Dict[str, torch.LongTensor]] = None,
        mention_left_context: Optional[Dict[str, torch.LongTensor]] = None,
        mention_right_context: Optional[Dict[str, torch.LongTensor]] = None,
        mention_context: Optional[Dict[str, torch.LongTensor]] = None,
        concept_id: Optional[torch.LongTensor] = None,
        concept_canonical_name: Optional[Dict[str, torch.LongTensor]] = None,
        concept_definition: Optional[Dict[str, torch.LongTensor]] = None,
        concept_semantic_types: Optional[torch.LongTensor] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:

        outputs = {"metadata": metadata}

        mention_embeddings = None
        concept_embeddings = None

        if mention_span is not None:
            mention_embeddings = self.get_mention_embeddings(
                mention_span=mention_span,
                mention_left_context=mention_left_context,
                mention_right_context=mention_right_context,
                mention_context=mention_context,
            )

            if self._prediction_mode:
                outputs["mention_embeddings"] = mention_embeddings.detach().cpu()

        if concept_id is not None:
            concept_embeddings = self.get_concept_embeddings(
                concept_canonical_name=concept_canonical_name,
                concept_definition=concept_definition,
                concept_semantic_types=concept_semantic_types,
            )

            if self._prediction_mode:
                outputs["concept_embeddings"] = concept_embeddings.detach().cpu()

        # if not self._prediction_mode:
        #     cosine_sim_matrix = self._cosine_matrix_attention(
        #         mention_embeddings.unsqueeze(0), concept_embeddings.unsqueeze(0)
        #     ).squeeze(0)

        #     cosine_sim_matrix = self._multiplier(
        #         cosine_sim_matrix.unsqueeze(-1)
        #     ).squeeze(-1)

        #     cosine_sim_matrix_prob = torch.sigmoid(cosine_sim_matrix.detach().cpu())

        #     num_instances = len(metadata)

        #     gold_labels = concept_id.unsqueeze(-1) == concept_id.unsqueeze(0)

        #     gold_labels_cpu = gold_labels.detach().cpu()

        #     num_corrects = (
        #         gold_labels_cpu[
        #             range(num_instances), cosine_sim_matrix_prob.argmax(dim=-1)
        #         ]
        #         .sum()
        #         .item()
        #     )

        #     self._recall_metric(num_corrects=num_corrects, num_instances=num_instances)

        #     outputs["loss"] = F.binary_cross_entropy_with_logits(
        #         input=cosine_sim_matrix, target=gold_labels.float()
        #     )

        return outputs

    # @overrides
    # def get_metrics(self, reset: bool = False) -> Dict[str, float]:
    #     recall = self._recall_metric.get_metric(reset)

    #     return {"recall": recall}
