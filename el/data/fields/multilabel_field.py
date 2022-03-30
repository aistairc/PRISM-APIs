# -*- coding: utf-8 -*-
from allennlp.data.fields.multilabel_field import MultiLabelField as MLF
from overrides import overrides


class MultiLabelField(MLF):
    @overrides
    def empty_field(self):
        return MultiLabelField(
            labels=[],
            label_namespace=self._label_namespace,
            skip_indexing=True,
            num_labels=self._num_labels,
        )
