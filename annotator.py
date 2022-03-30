# -*- coding: utf-8 -*-
import itertools
import os
import subprocess
import tempfile
from functools import lru_cache

import faiss
import numpy as np
from allennlp.common.util import import_submodules
from allennlp.models.archival import load_archive
from allennlp.predictors.predictor import Predictor
from loguru import logger
from pytorch_transformers.tokenization_bert import BasicTokenizer

from predictor import load_model, load_parameters, process_dir
from utils import file_utils
from utils.annotation import (
    NormalizationAnnotation,
    TextAnnotations,
    TextBoundAnnotationWithText,
)

import_submodules("el")

CACHE_SIZE = 0

TOKENIZER = BasicTokenizer(do_lower_case=False)


def batchify(instances, batch_size):
    for i in range(0, len(instances), batch_size):
        yield instances[i : i + batch_size]


class Standoffizer:
    def __init__(self, text, subs, start=0):
        self.text = text
        self.subs = subs
        self.start = start

    def __iter__(self):
        offset = 0

        for sub in self.subs:
            pos = self.text.index(sub, offset)
            offset = pos + len(sub)
            yield (self.start + pos, self.start + offset)


class GeniassSentenceSplitter:
    def __init__(self, geniass_dir, cache_dir):
        self.geniass_dir = geniass_dir
        self.cache_dir = cache_dir

    def split_sentences(self, doc):
        file_utils.make_dirs(self.cache_dir)

        with tempfile.TemporaryDirectory(
            dir=self.cache_dir
        ) as dirname, tempfile.NamedTemporaryFile(
            mode="w+", encoding="UTF-8", dir=dirname
        ) as cache_file:
            original_doc_file = cache_file.name
            processed_doc_file = original_doc_file + ".res"

            cache_file.write(doc)
            cache_file.flush()  # Make sure to have this line

            subprocess.run(
                args=["./geniass", original_doc_file, processed_doc_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self.geniass_dir,
                check=True,
            )

            process = subprocess.run(
                args=["perl", "geniass-postproc.pl", processed_doc_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=self.geniass_dir,
                check=True,
                encoding="UTF-8",
            )

            return list(filter(None, map(str.strip, process.stdout.split("\n"))))


class DeepEMAnnotator:
    def __init__(self, config_file, geniass_dir, cache_dir):
        self.config_file = config_file
        self.geniass_dir = geniass_dir
        self.cache_dir = cache_dir

        self.input_dir = os.path.join(self.cache_dir, "inputs")
        self.output_dir = os.path.join(self.cache_dir, "outputs")

        self.parameters = load_parameters(self.config_file)
        self.model = load_model(self.parameters)

        self.geniass = GeniassSentenceSplitter(
            self.geniass_dir, os.path.join(self.cache_dir, "geniass")
        )

    @lru_cache(maxsize=CACHE_SIZE)
    def __call__(self, doc):
        with TextAnnotations(text=doc) as annotator:
            sentence_standoffs = []
            token_standoffs = []

            try:
                sentences = self.geniass.split_sentences(doc)

                sentence_standoffs.extend(Standoffizer(doc, sentences))

                tokenized_sentences = []
                tokens = []

                for sentence, (sentence_start, _) in zip(sentences, sentence_standoffs):
                    tokenized_sentence = TOKENIZER.tokenize(sentence)

                    tokenized_sentences.append(" ".join(tokenized_sentence))
                    tokens.extend(tokenized_sentence)

                    token_standoffs.extend(
                        Standoffizer(sentence, tokenized_sentence, sentence_start)
                    )

                if len(tokenized_sentences) == 0:
                    return annotator, sentence_standoffs, token_standoffs

                tokenized_doc = "\n".join(tokenized_sentences)

                offset_map = dict(
                    zip(
                        itertools.chain.from_iterable(
                            Standoffizer(tokenized_doc, tokens)
                        ),
                        itertools.chain.from_iterable(token_standoffs),
                    )
                )

                file_utils.make_dirs(self.input_dir)
                file_utils.make_dirs(self.output_dir)

                with tempfile.TemporaryDirectory(
                    dir=self.input_dir
                ) as input_dir, tempfile.TemporaryDirectory(
                    dir=self.output_dir
                ) as output_dir:
                    sample_filename = "sample"

                    file_utils.write_text(
                        tokenized_doc, os.path.join(input_dir, sample_filename + ".txt")
                    )
                    file_utils.write_lines(
                        [], os.path.join(input_dir, sample_filename + ".ann")
                    )

                    process_dir(
                        self.model, self.parameters, input_dir + "/", output_dir + "/"
                    )

                    prediction_dir = os.path.join(output_dir, "ev-last/ev-ann")

                    if not os.path.isdir(prediction_dir):
                        prediction_dir = os.path.join(output_dir, "rel-last/rel-ann")

                    with TextAnnotations(
                        document=os.path.join(prediction_dir, sample_filename)
                    ) as prediction:
                        self.__fix_annotations(annotator, prediction, offset_map)

            except Exception as ex:
                logger.exception(ex)

            return annotator, sentence_standoffs, token_standoffs

    @staticmethod
    def __fix_annotations(annotator, prediction, offset_map):
        # V1: No filter
        # for entity in prediction.get_textbounds():
        #     TextBoundAnnotationWithText(
        #         id=entity.id,
        #         spans=[(offset_map[ss], offset_map[se]) for ss, se in entity.spans],
        #         type=entity.type,
        #         text=annotator,
        #     )

        # for relation in prediction.get_relations():
        #     annotator.add_annotation(relation)

        # for event in prediction.get_events():
        #     annotator.add_annotation(event)

        # for attribute in prediction.get_attributes():
        #     annotator.add_annotation(attribute)

        # V2: Filter duplicates
        seen_entities = {}
        identical_entities = {}

        num_entities = 0
        num_duplicate_entities = 0

        for entity in prediction.get_textbounds():
            num_entities += 1

            spans = tuple((offset_map[ss], offset_map[se]) for ss, se in entity.spans)

            if (entity.type, spans) in seen_entities:
                num_duplicate_entities += 1

                logger.info(
                    "Skipped duplicate entity: {} -> {}",
                    entity.id,
                    seen_entities[entity.type, spans],
                )
            else:
                TextBoundAnnotationWithText(
                    id=entity.id,
                    spans=spans,
                    type=entity.type,
                    text=annotator,
                )

                seen_entities[entity.type, spans] = entity.id

            identical_entities[entity.id] = seen_entities[entity.type, spans]

        logger.info(
            "Removed {}/{} ({:.2f}%) duplicate entities",
            num_duplicate_entities,
            num_entities,
            num_entities and num_duplicate_entities / num_entities * 100,
        )

        seen_relations = {}

        num_relations = 0
        num_duplicate_relations = 0

        for relation in prediction.get_relations():
            num_relations += 1

            arg_1 = relation.arg1 = identical_entities[relation.arg1]
            arg_2 = relation.arg2 = identical_entities[relation.arg2]

            if (relation.type, arg_1, arg_2) in seen_relations:
                num_duplicate_relations += 1

                logger.info(
                    "Skipped duplicate relation: {} -> {}",
                    relation.id,
                    seen_relations[relation.type, arg_1, arg_2],
                )
            else:
                annotator.add_annotation(relation)

                seen_relations[relation.type, arg_1, arg_2] = relation.id

        logger.info(
            "Removed {}/{} ({:.2f}%) duplicate relations",
            num_duplicate_relations,
            num_relations,
            num_relations and num_duplicate_relations / num_relations * 100,
        )

        events = {event.id: event for event in prediction.get_events()}

        seen_events = {}
        identical_events = {}

        num_events = len(events)
        num_duplicate_events = 0

        def add_unique_event(event):
            event.trigger = identical_entities[event.trigger]

            event_hash = (event.type, event.trigger)

            args = []

            for arg_role, arg_id in event.args:
                if arg_id.startswith("E"):
                    if arg_id not in identical_events:
                        add_unique_event(events[arg_id])

                    arg_id = identical_events[arg_id]
                else:
                    arg_id = identical_entities[arg_id]

                args.append((arg_role, arg_id))

            event_hash += tuple(sorted(args))

            is_valid_event = event_hash not in seen_events

            if is_valid_event:
                event.args = args

                annotator.add_annotation(event)

                seen_events[event_hash] = event.id
            else:
                logger.info(
                    "Skipped duplicate event: {} -> {}",
                    event.id,
                    seen_events[event_hash],
                )

            identical_events[event.id] = seen_events[event_hash]

            return is_valid_event

        for event in prediction.get_events():
            if not add_unique_event(event):
                num_duplicate_events += 1

        logger.info(
            "Removed {}/{} ({:.2f}%) duplicate events",
            num_duplicate_events,
            num_events,
            num_events and num_duplicate_events / num_events * 100,
        )

        seen_attributes = {}

        num_attributes = 0
        num_duplicate_attributes = 0

        for attribute in prediction.get_attributes():
            num_attributes += 1

            attribute.target = identical_events[attribute.target]

            if (attribute.type, attribute.target, attribute.value) in seen_attributes:
                num_duplicate_attributes += 1

                logger.info(
                    "Skipped duplicate attribute: {} -> {}",
                    attribute.id,
                    seen_attributes[attribute.type, attribute.target, attribute.value],
                )
            else:
                annotator.add_annotation(attribute)

                seen_attributes[
                    attribute.type, attribute.target, attribute.value
                ] = attribute.id

        logger.info(
            "Removed {}/{} ({:.2f}%) duplicate attributes",
            num_duplicate_attributes,
            num_attributes,
            num_attributes and num_duplicate_attributes / num_attributes * 100,
        )


class NERPredictor:
    def __init__(self, model_dir, batch_size=32, cuda_device=-1):
        self.model_dir = model_dir
        self.batch_size = batch_size
        self.cuda_device = cuda_device

        self.predictor = Predictor.from_archive(
            load_archive(self.model_dir, cuda_device=self.cuda_device)
        )

    def __call__(self, tokenized_sentences):
        docs = {
            "sample.ann": {
                "sentences": [
                    {"tokens": tokens, "mentions": []} for tokens in tokenized_sentences
                ]
            }
        }

        instances = list(self.predictor._dataset_reader._read(docs))

        for batch in batchify(instances, self.batch_size):
            predictions = self.predictor.predict_batch_instance(batch)

            assert len(batch) == len(predictions)

            for prediction in predictions:
                self.predictor.process_predictions(prediction, docs)

        for doc in docs.values():
            num_mentions = 0

            for sentence in doc["sentences"]:
                for mention in sentence["mentions"]:
                    num_mentions += 1
                    mention["id"] = f"T{num_mentions}"

        return docs


class CGPredictor:
    def __init__(
        self,
        model_dir,
        faiss_indexer,
        concepts,
        top_k=50,
        batch_size=512,
        cuda_device=-1,
    ):
        self.model_dir = model_dir
        self.faiss_indexer = faiss_indexer
        self.concepts = concepts
        self.top_k = top_k
        self.batch_size = batch_size
        self.cuda_device = cuda_device

        self.predictor = Predictor.from_archive(
            load_archive(self.model_dir, cuda_device=self.cuda_device)
        )

    def __call__(self, docs):
        mention_map = {}

        for doc_id, doc in docs.items():
            for sentence in doc["sentences"]:
                for mention in sentence["mentions"]:
                    mention_map[doc_id, mention["id"]] = mention["references"]

        instances = list(self.predictor._dataset_reader._read(docs))

        for batch in batchify(instances, self.batch_size):
            predictions = self.predictor.predict_batch_instance(batch)

            assert len(batch) == len(predictions)

            mention_ids = [
                (
                    prediction["metadata"]["mention"]["doc_id"],
                    prediction["metadata"]["mention"]["mention_id"],
                )
                for prediction in predictions
            ]

            mention_embeddings = np.array(
                [prediction["mention_embeddings"] for prediction in predictions],
                dtype=np.float32,
            )

            faiss.normalize_L2(mention_embeddings)

            similarities, queries = self.faiss_indexer.search(
                mention_embeddings, self.top_k
            )

            assert len(mention_ids) == len(similarities) == len(queries)

            for (
                mention_id,
                nearest_concept_similarities,
                nearest_concept_indices,
            ) in zip(mention_ids, similarities, queries):

                nearest_concepts = [
                    (concept_similarity, *self.concepts["ids"][concept_index])
                    for concept_similarity, concept_index in zip(
                        nearest_concept_similarities, nearest_concept_indices
                    )
                ]

                for concept_similarity, concept_id, alias_index in nearest_concepts:
                    mention_map[mention_id][
                        "PRED", f"{concept_id}/{alias_index}"
                    ] = concept_similarity

        return docs


class CRPredictor:
    def __init__(self, model_dir, batch_size=128, cuda_device=-1):
        self.model_dir = model_dir
        self.batch_size = batch_size
        self.cuda_device = cuda_device

        self.predictor = Predictor.from_archive(
            load_archive(self.model_dir, cuda_device=self.cuda_device)
        )

    def __call__(self, docs):
        mention_map = {}

        for doc_id, doc in docs.items():
            for sentence in doc["sentences"]:
                for mention in sentence["mentions"]:
                    mention_map[doc_id, mention["id"]] = mention

        instances = list(self.predictor._dataset_reader._read(docs))

        for batch in batchify(instances, self.batch_size):
            predictions = self.predictor.predict_batch_instance(batch)

            assert len(batch) == len(predictions)

            for prediction in predictions:
                self.predictor.process_predictions(prediction, mention_map)

        return docs


class SemELAnnotator:
    def __init__(
        self,
        ner_dir,
        cg_dir,
        cr_dir,
        kbe_dir,
        geniass_dir,
        cache_dir,
        enable_linking=True,
    ):
        self.ner_dir = ner_dir
        self.cg_dir = cg_dir
        self.cr_dir = cr_dir
        self.kbe_dir = kbe_dir
        self.geniass_dir = geniass_dir
        self.cache_dir = cache_dir
        self.enable_linking = enable_linking

        self.ner_predictor = NERPredictor(self.ner_dir)

        if self.enable_linking:
            self.concepts = file_utils.read_json(
                os.path.join(self.kbe_dir, "concepts.json")
            )

            self.concept_embeddings = np.memmap(
                filename=os.path.join(self.kbe_dir, "normed_concept_embeddings.npy"),
                dtype=np.float32,
                mode="r",
                shape=tuple(self.concepts["size"]),
            )

            self.faiss_indexer = faiss.IndexFlatIP(self.concept_embeddings.shape[-1])
            self.faiss_indexer.add(self.concept_embeddings)

            self.cg_predictor = CGPredictor(
                self.cg_dir, self.faiss_indexer, self.concepts
            )
            self.cr_predictor = CRPredictor(self.cr_dir)

        self.geniass = GeniassSentenceSplitter(
            self.geniass_dir, os.path.join(self.cache_dir, "geniass")
        )

    @lru_cache(maxsize=CACHE_SIZE)
    def __call__(self, doc):
        with TextAnnotations(text=doc) as annotator:
            sentence_standoffs = []
            token_standoffs = []

            try:
                sentences = self.geniass.split_sentences(doc)

                sentence_standoffs.extend(Standoffizer(doc, sentences))

                tokenized_sentences = []

                offset_maps = []

                for sentence, (sentence_start, _) in zip(sentences, sentence_standoffs):
                    tokenized_sentence = TOKENIZER.tokenize(sentence)

                    tokenized_sentences.append(tokenized_sentence)

                    sentence_token_standoffs = list(
                        Standoffizer(sentence, tokenized_sentence, sentence_start)
                    )

                    token_standoffs.extend(sentence_token_standoffs)

                    offset_maps.append(sentence_token_standoffs)

                if len(tokenized_sentences) == 0:
                    return annotator, sentence_standoffs, token_standoffs

                prediction = self.ner_predictor(tokenized_sentences)

                if self.enable_linking:
                    prediction = self.cg_predictor(prediction)
                    prediction = self.cr_predictor(prediction)

                prediction = prediction["sample.ann"]

                self.__fix_annotations(annotator, prediction, offset_maps)

            except Exception as ex:
                logger.exception(ex)

            return annotator, sentence_standoffs, token_standoffs

    @staticmethod
    def __fix_annotations(annotator, prediction, offset_maps):
        sentences = prediction["sentences"]

        assert len(sentences) == len(offset_maps)

        for sentence, offset_map in zip(sentences, offset_maps):
            for mention in sentence["mentions"]:
                mention_id = annotator.get_new_id("T")

                TextBoundAnnotationWithText(
                    id=mention_id,
                    spans=[
                        (offset_map[mention["start"]][0], offset_map[mention["end"]][1])
                    ],
                    type=mention["label"],
                    text=annotator,
                )

                for (source, concept_id), confidence in mention["references"].items():
                    if source.startswith("PRED"):
                        norm_id = annotator.get_new_id("N")

                        annotator.add_annotation(
                            NormalizationAnnotation(
                                id=norm_id,
                                type="Reference",
                                target=mention_id,
                                refdb="UMLS",
                                refid=concept_id,
                                tail=f"\tConf: {confidence}",
                            )
                        )


if __name__ == "__main__":
    from glob import glob

    # Event Extraction
    # annotator = DeepEMAnnotator(
    #     config_file="experiments/ipf_genes_20210406_10_folds_fold-9/ev/configs/predict-e2e-raw.yaml",
    #     geniass_dir="tools/geniass",
    #     cache_dir=".cache",
    # )

    # Relation Extraction
    # annotator = DeepEMAnnotator(
    #     config_file="experiments/ipf_genes_20210406_10_folds_fold-6/rel/configs/predict-e2e-raw.yaml",
    #     geniass_dir="tools/geniass",
    #     cache_dir=".cache",
    # )

    # Entity Linking
    # annotator = SemELAnnotator(
    #     ner_dir="experiments/ner_ipf_genes_merged_pr2-10-folds_fold-2",
    #     cg_dir="experiments/cg_ipf_genes_merged_pr2-10-folds_fold-2",
    #     cr_dir="experiments/cr_ipf_genes_merged_pr2-10-folds_fold-2",
    #     kbe_dir="experiments/cg_ipf_genes_merged_pr2-10-folds_fold-2-umls",
    #     geniass_dir="tools/geniass",
    #     cache_dir=".cache",
    #     enable_linking=True,
    # )

    input_dir = "data/samples"
    output_dir = ".cache/samples"

    for input_file in glob(os.path.join(input_dir, "*.txt")):
        output_file, _ = os.path.splitext(
            os.path.join(output_dir, os.path.relpath(input_file, input_dir))
        )

        doc = file_utils.read_text(input_file)

        annotations, sentence_standoffs, token_standoffs = annotator(doc)

        file_utils.write_text(doc, output_file + ".txt")
        file_utils.write_text(str(annotations), output_file + ".ann")
