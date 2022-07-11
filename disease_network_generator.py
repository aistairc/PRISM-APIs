# -*- coding: utf-8 -*-
import itertools
import os
from collections import namedtuple
from glob import glob

import pandas as pd
import requests
from loguru import logger

import disease_network_generator_for_2d
import disease_network_generator_for_3d
from utils import file_utils

ENTITY = namedtuple(
    "Entity", ["id", "type", "spans", "umls_id", "canonical_name", "text"]
)
NORMALIZATION = namedtuple(
    "Normalization", ["id", "type", "target", "refdb", "refid", "tail"]
)
EVENT = namedtuple("Event", ["id", "trigger", "args"])


def annotate(task, doc):
    try:
        res = requests.post(
            f"http://127.0.0.1:9091/{task}/annotate", data={"text": doc}
        )

        res.raise_for_status()

        annotations = res.json()

        entities = annotations["entities"] + annotations["triggers"]
        norms = annotations["normalizations"]
        cuis = annotations["cui_data"]
        events = annotations["events"]

        entities = [ENTITY(*(e + [None, None, None])) for e in entities]
        norms = [NORMALIZATION(*n) for n in norms]
        events = [EVENT(*e) for e in events]

        return entities, norms, cuis, events
    except requests.HTTPError as ex:
        logger.exception(ex)

    return [], [], {}, []


def generate_status(doc_idx, num_docs, status, status_file):
    file_utils.write_json(
        {"current": doc_idx, "total": num_docs, "status": status}, status_file
    )


def generate_graph_data(
    docs,
    output_file_for_2d,
    output_file_for_3d,
    status_file,
):
    max_args = 0
    all_events = []

    for doc_idx, (doc_name, doc) in enumerate(docs, start=1):
        el_entities, el_norms, el_cuis, _ = annotate("entity_linking", doc)
        ev_entities, _, _, ev_events = annotate("event_extraction", doc)

        norm_map = {}

        entities = {e.id: e for e in el_entities}

        for norm in el_norms:
            e = entities[norm.target]
            span_starts, span_ends = zip(*e.spans)
            span_start, span_end = min(span_starts), max(span_ends)

            norm_map[span_start, span_end] = {
                "id": norm.refid,
                "name": el_cuis[norm.refid],
            }

        entities = {e.id: e for e in ev_entities}
        events = {ev.id: ev for ev in ev_events}

        for e_id, e in entities.items():
            span_starts, span_ends = zip(*e.spans)
            span_start, span_end = min(span_starts), max(span_ends)

            norm = norm_map.get(
                (span_start, span_end),
                {
                    "id": None,
                    "name": None,
                },
            )

            entities[e_id] = entities[e_id]._replace(umls_id=norm["id"])
            entities[e_id] = entities[e_id]._replace(canonical_name=norm["name"])
            entities[e_id] = entities[e_id]._replace(text=doc[span_start:span_end])

        for ev in events.values():
            max_args = max(max_args, len(ev.args))

            obj = {
                # "corpus_name": "ipf_genes_20210127",
                "article_id": doc_name,
                "event_id": ev.id,
                "event_type": entities[ev.trigger].type,
                "trigger_id": ev.trigger,
                "trigger_str": entities[ev.trigger].text,
                "trigger_canonical_name": entities[ev.trigger].canonical_name,
                "trigger_umls_id": entities[ev.trigger].umls_id,
            }

            for arg_index, (arg_role, arg_id) in enumerate(ev.args, start=1):
                if arg_id.startswith("E"):
                    arg_id = events[arg_id].trigger

                obj[f"argument_id_{arg_index}"] = arg_id
                obj[f"argument_type_{arg_index}"] = entities[arg_id].type
                obj[f"argument_str_{arg_index}"] = entities[arg_id].text
                obj[f"argument_canonical_name_{arg_index}"] = entities[
                    arg_id
                ].canonical_name
                obj[f"argument_umls_id_{arg_index}"] = entities[arg_id].umls_id
                obj[f"argument_role_type_{arg_index}"] = arg_role

            all_events.append(obj)

        generate_status(doc_idx, len(docs), False, status_file)

    logger.info("Max args: {}", max_args)

    cols = [
        # "corpus_name",
        "article_id",
        "event_id",
        "event_type",
        "trigger_id",
        "trigger_str",
        "trigger_canonical_name",
        "trigger_umls_id",
    ]

    for arg_index in range(1, max_args + 1):
        cols.append(f"argument_id_{arg_index}")
        cols.append(f"argument_type_{arg_index}")
        cols.append(f"argument_str_{arg_index}")
        cols.append(f"argument_canonical_name_{arg_index}")
        cols.append(f"argument_umls_id_{arg_index}")
        cols.append(f"argument_role_type_{arg_index}")

    all_events_for_2d = []
    all_events_for_3d = []

    for ev in all_events:
        all_events_for_2d.append({col: ev.get(col, None) for col in cols})

        arg_indices = [
            arg_index
            for arg_index in range(1, max_args + 1)
            if f"argument_id_{arg_index}" in ev
        ]

        if len(arg_indices) > 1:
            for arg_index_1, arg_index_2 in itertools.combinations(arg_indices, 2):
                all_events_for_3d.append(
                    (
                        "["
                        + str(ev.get(f"argument_type_{arg_index_1}", None))
                        + ", "
                        + str(ev.get(f"argument_umls_id_{arg_index_1}", None))
                        + ", "
                        + str(ev.get(f"argument_canonical_name_{arg_index_1}", None))
                        + "]: "
                        + str(ev.get(f"argument_str_{arg_index_1}", None)),
                        str(ev.get(f"argument_type_{arg_index_1}", None)),
                        "["
                        + str(ev.get(f"argument_type_{arg_index_2}", None))
                        + ", "
                        + str(ev.get(f"argument_umls_id_{arg_index_2}", None))
                        + ", "
                        + str(ev.get(f"argument_canonical_name_{arg_index_2}", None))
                        + "]: "
                        + str(ev.get(f"argument_str_{arg_index_2}", None)),
                        str(ev.get(f"argument_type_{arg_index_2}", None)),
                    )
                )

    graph_data_for_2d = disease_network_generator_for_2d.get_graph_data(
        all_events_for_2d
    )

    df = pd.DataFrame(
        all_events_for_3d, columns=["SRC_NAME", "SRC_TYPE", "DST_NAME", "DST_TYPE"]
    )
    if not all_events_for_3d:
        df.index = df.index.astype(int)

    graph_data_for_3d = disease_network_generator_for_3d.get_graph_data(df)

    file_utils.write_json(graph_data_for_2d, output_file_for_2d)
    disease_network_generator_for_3d.save_graph(graph_data_for_3d, output_file_for_3d)

    generate_status(len(docs), len(docs), True, status_file)


if __name__ == "__main__":
    input_dir = "data/samples"
    output_dir = ".cache/samples"

    output_file_for_2d = os.path.join(output_dir, "2d_disease_network.json")
    output_file_for_3d = os.path.join(output_dir, "3d_disease_network.html")

    status_file = os.path.join(output_dir, "status.json")

    docs = [
        (os.path.basename(input_file), file_utils.read_text(input_file))
        for input_file in glob(os.path.join(input_dir, "*.txt"))
    ]

    generate_graph_data(
        docs,
        output_file_for_2d,
        output_file_for_3d,
        status_file,
    )
