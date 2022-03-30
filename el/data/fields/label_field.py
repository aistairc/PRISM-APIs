# -*- coding: utf-8 -*-
from typing import Union

from allennlp.data.fields.label_field import LabelField as LF
from overrides import overrides


class LabelField(LF):
    def __init__(
        self,
        label: Union[str, int],
        label_namespace: str = "labels",
        skip_indexing: bool = False,
        padding_value: int = -1,
    ) -> None:
        super().__init__(
            label=label, label_namespace=label_namespace, skip_indexing=skip_indexing
        )
        self._padding_value = padding_value

    @overrides
    def empty_field(self):
        return LabelField(
            label=self._padding_value,
            label_namespace=self._label_namespace,
            skip_indexing=True,
            padding_value=self._padding_value,
        )
