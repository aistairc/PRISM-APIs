# -*- coding: utf-8 -*-
import math

import torch
from allennlp.nn.activations import Activation


@Activation.register("smooth_gelu")
class SmoothGelu(Activation):
    def __call__(self, tensor: torch.Tensor) -> torch.Tensor:
        """
        Implementation of the gelu activation function currently in Google Bert repo (identical to OpenAI GPT).
        Also see https://arxiv.org/abs/1606.08415
        """
        return (
            0.5
            * tensor
            * (
                1
                + torch.tanh(
                    math.sqrt(2 / math.pi) * (tensor + 0.044715 * torch.pow(tensor, 3))
                )
            )
        )
