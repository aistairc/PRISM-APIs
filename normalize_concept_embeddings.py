# -*- coding: utf-8 -*-
import faiss
import numpy as np

from utils import file_utils

concepts = file_utils.read_json(
    "experiments/cg_ipf_genes_merged_pr2-10-folds_fold-2-umls/concepts.json"
)

concept_embeddings = np.memmap(
    filename="experiments/cg_ipf_genes_merged_pr2-10-folds_fold-2-umls/concept_embeddings.npy",
    dtype=np.float32,
    mode="c",
    shape=tuple(concepts["size"]),
)

faiss.normalize_L2(concept_embeddings)

normed_concept_embeddings = np.memmap(
    filename="experiments/cg_ipf_genes_merged_pr2-10-folds_fold-2-umls/normed_concept_embeddings.npy",
    dtype=np.float32,
    mode="w+",
    shape=tuple(concepts["size"]),
)

normed_concept_embeddings[:] = concept_embeddings[:]
normed_concept_embeddings.flush()

del normed_concept_embeddings
del concept_embeddings
