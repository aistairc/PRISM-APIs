# -*- coding: utf-8 -*-
import itertools
import os
from collections import namedtuple, defaultdict, Counter
from types import SimpleNamespace
from enum import IntEnum
from glob import glob

import pandas as pd
import requests
from loguru import logger

import disease_network_generator_for_2d
import disease_network_generator_for_3d
from utils import file_utils



ANTECEDENT_ROLES = ["Cause", "disorder"]
CONSEQUENT_ROLE = "Theme"
POSITIVE_REGULATION = "Positive_regulation"
NEGATIVE_REGULATION = "Negative_regulation"
REGULATION_EVENT_TYPES = { POSITIVE_REGULATION, NEGATIVE_REGULATION }
DIRECT = "Regulation"
class Regulation(IntEnum):
    UNREGULATED = 0
    POSITIVE = 1
    NEGATIVE = -1

    @classmethod
    def for_type(cls, t):
        if t.type == POSITIVE_REGULATION:
            return cls.POSITIVE
        elif t.type == NEGATIVE_REGULATION:
            return cls.NEGATIVE
        else:
            return cls.UNREGULATED

ENTITY = namedtuple(
    "Entity", ["id", "type", "spans", "umls_id", "canonical_name", "text"]
)
NORMALIZATION = namedtuple(
    "Normalization", ["id", "type", "target", "refdb", "refid", "tail"]
)
EVENT = namedtuple("Event", ["id", "trigger", "args", "regulation"], defaults=[Regulation.UNREGULATED])

EXTERNAL_API_BASE_URL = os.environ.get('EXTERNAL_API_BASE_URL', 'http://127.0.0.1:9091')


def annotate(task, doc):
    try:
        uri = f"{EXTERNAL_API_BASE_URL}/{task}/annotate"
        res = requests.post(uri, data={"text": doc})

        res.raise_for_status()

        annotations = res.json()

        entities = annotations["entities"] + annotations["triggers"]
        norms = annotations["normalizations"]
        cuis = annotations["cui_data"]
        events = annotations["events"]

        entities = [ENTITY(*(e + [None, None, None])) for e in entities]
        ev_entity_map = {e.id: e for e in entities}
        norms = [NORMALIZATION(*n) for n in norms]
        events = [EVENT(*e, Regulation.for_type(ev_entity_map[e[1]])) for e in events]

        return entities, norms, cuis, events, annotations
    except requests.HTTPError as ex:
        logger.exception(ex)

    return [], [], {}, []


class RegulationSquasher:
    def __init__(self):
        self.node_list = []
        self.node_key_map = {}
        self.link_list = []
        self.link_key_map = {}

    def add(self, doc_name, entities, events):
        node_map = {}
        link_map = {}
        entity_map = {}
        event_map = {}

        # entities
        for entity in entities.values():
            entity_map[entity.id] = entity
            node_key = entity.umls_id or f'"{entity.text}"'
            node = self.node_key_map.get(node_key)
            if not node:
                node = {
                    "id": len(self.node_list),
                    "name": entity.canonical_name or f'"{entity.text}"',
                    "instances": [],
                    "cui": entity.umls_id,
                    "url": entity.umls_id and "https://uts.nlm.nih.gov/uts/umls/searchResults?searchString=" + entity.umls_id,
                }
                self.node_list.append(node)
                self.node_key_map[node_key] = node
            node["instances"].append({
                "doc": doc_name,
                "brat_ids": [[entity.id]],
                "type": entity.type,
            })

        # events
        for event in events.values():
            event_map[event.id] = event

        regulation_events = defaultdict(list)
        reg_regulation_events = []
        for event in events.values():
            trigger = entity_map[event.trigger]
            if trigger.type in REGULATION_EVENT_TYPES:
                antecedents = [arg for arg in event.args if arg[0] in ANTECEDENT_ROLES]
                for antecedent_role, antecedent_id in antecedents:
                    antecedent = entity_map.get(antecedent_id)
                    if not antecedent:
                        # antecedent must be an entity
                        continue
                    antecedent_node_key = antecedent.umls_id or f'"{antecedent.text}"'
                    antecedent_node = self.node_key_map[antecedent_node_key]

                    consequents = [arg for arg in event.args if arg[0] == CONSEQUENT_ROLE]
                    for consequent_role, consequent_id in consequents:
                        consequent = entity_map.get(consequent_id)
                        if consequent:
                            # consequent is an entity
                            consequent_node_key = consequent.umls_id or f'"{consequent.text}"'
                            consequent_node = self.node_key_map[consequent_node_key]

                            brat_ids = [[event.id], [trigger.id], [antecedent_id], [consequent_id]]
                            regulation_events[event.id].append([True, antecedent_node, consequent_node, event.regulation, DIRECT, brat_ids])
                        else:
                            # consequent is event
                            consequent_event = event_map[consequent_id]
                            consequent_type = entity_map[consequent_event.trigger].type
                            sub_consequents = [arg for arg in consequent_event.args if arg[0] == CONSEQUENT_ROLE]
                            if not sub_consequents:
                                # must have consequents
                                continue
                            for sub_consequent_role, sub_consequent_id in sub_consequents:
                                if consequent_type in REGULATION_EVENT_TYPES:
                                    # consequent is a regulation event
                                    # XXX add arc is as well? look up format
                                    brat_ids = [[event.id], [trigger.id], [antecedent_id]] # consequent will be added later
                                    regulation = Regulation(consequent_event.regulation * event.regulation)
                                    event_descriptor = (True, event.id, antecedent_node, sub_consequent_id, regulation, brat_ids)
                                    reg_regulation_events.append(event_descriptor)
                                else:
                                    # consequent is a non-regulation event
                                    sub_consequent = entity_map.get(sub_consequent_id)
                                    if not sub_consequent:
                                        # sub consequent must be an entity
                                        continue
                                    # XXX add arc is as well? look up format
                                    sub_consequent_node_key = sub_consequent.umls_id or f'"{sub_consequent.text}"'
                                    sub_consequent_node = self.node_key_map[sub_consequent_node_key]
                                    brat_ids = [[event.id], [trigger.id], [antecedent_id], [consequent_id], [sub_consequent_id]]
                                    event_descriptor = [True, antecedent_node, sub_consequent_node, event.regulation, consequent_type, brat_ids]
                                    regulation_events[event.id].append(event_descriptor)

        changed = True
        while reg_regulation_events and changed:
            changed = False # to detect dependency cycles
            for reg_event_ix in range(len(reg_regulation_events)):
                event_descriptor = reg_regulation_events[reg_event_ix]
                _, event_id, antecedent_node, consequent_id, regulation, brat_ids = event_descriptor
                consequent_reg_events = regulation_events.get(consequent_id)
                if not consequent_reg_events:
                    # Not generated yet
                    continue
                for consequent_reg_event in consequent_reg_events:
                    changed = True
                    _, _, sub_consequent_node, sub_regulation, sub_consequent_type, sub_brat_ids = consequent_reg_event
                    new_regulation = Regulation(consequent_event.regulation * event.regulation)
                    new_brat_ids = brat_ids + sub_brat_ids
                    new_event_descriptor = [True, antecedent_node, sub_consequent_node, new_regulation, sub_consequent_type, new_brat_ids]
                    regulation_events[event_id] = new_event_descriptor
                    consequent_reg_event[0] = False
                event_descriptor[0] = False

            # delete the processed reg_regulation_events
            reg_regulation_events = [
                event_descriptor for event_descriptor in reg_regulation_events if event_descriptor[0]
            ]


        for event_descriptors in regulation_events.values():
            for event_descriptor in event_descriptors:
                if not event_descriptor[0]:
                    # ignore any reg_regulation_events remaining, as they are cyclic
                    continue

                _, antecedent_node, consequent_node, regulation, consequent_type, brat_ids = event_descriptor
                link_key = (antecedent_node["id"], consequent_node["id"])
                link = self.link_key_map.get(link_key)
                if not link:
                    link = {
                        "id": len(self.link_list),
                        "source": antecedent_node["id"],
                        "target": consequent_node["id"],
                        "instances": [],
                    }
                    self.link_key_map[link_key] = link
                    self.link_list.append(link)

                    # see if there is an edge going the other way
                    rev_link_key = (consequent_node["id"], antecedent_node["id"])
                    rev_link = self.link_key_map.get(rev_link_key)
                    if rev_link:
                        link["bidir"] = 0
                        rev_link["bidir"] = 1

                link["instances"].append({
                    "type": consequent_type,
                    "regulation": regulation,
                    "doc": doc_name,
                    "brat_ids": brat_ids,
                })

    def graph_data(self):
        return {
            "nodes": self.node_list,
            "links": self.link_list,
        }


def generate_status(doc_idx, num_docs, status, status_file):
    file_utils.write_json(
        {"current": doc_idx, "total": num_docs, "status": status}, status_file
    )


def generate_graph_data(
    docs,
    output_file_for_graph,
    output_file_for_2d,
    output_file_for_3d,
    status_file,
):
    max_args = 0
    all_events = []
    doc_anns = {}
    regulation_squasher = RegulationSquasher()

    for doc_idx, (doc_name, doc) in enumerate(docs, start=1):
        # el_entities, el_norms, el_cuis, _ = annotate("entity_linking", doc)
        # ev_entities, _, _, ev_events = annotate("event_extraction", doc)
        if isinstance(doc_name, tuple): # GTDEBUG
            el_entities, el_norms, el_cuis, ev_entities, ev_events = doc_name
            doc_name = "DEBUG"

            el_entities = [ENTITY(*e) for e in el_entities]
            el_norms = [NORMALIZATION(*n) for n in el_norms]
            ev_entities = [ENTITY(*e) for e in ev_entities]
            ev_entity_map = {e.id: e for e in ev_entities}
            ev_events = [EVENT(*e, Regulation.for_type(ev_entity_map[e[1]])) for e in ev_events]
            # TODO make sure `annotate` detects regulation

        else:
            el_entities, el_norms, el_cuis, _, _ = annotate("entity_linking", doc)
            ev_entities, _, _, ev_events, anns = annotate("event_extraction", doc)
            doc_anns[doc_name] = anns

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

        regulation_squasher.add(doc_name, entities, events)

        for ev in events.values():
            max_args = max(max_args, len(ev.args))

            obj = {
                # "corpus_name": "ipf_genes_20210127",
                "article_id": doc_name,
                "event_id": ev.id,
                "event_type": entities[ev.trigger].type,
                "event_regulation": int(ev.regulation),
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

    graph = regulation_squasher.graph_data()
    logger.info("Max args: {}", max_args)

    cols = [
        # "corpus_name",
        "article_id",
        "event_id",
        "event_type",
        "event_regulation",
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
                        ev.get("event_regulation", None),
                    )
                )

    graph_data_for_2d = disease_network_generator_for_2d.get_graph_data(
        all_events_for_2d
    )
    df = pd.DataFrame(
        all_events_for_3d, columns=["SRC_NAME", "SRC_TYPE", "DST_NAME", "DST_TYPE", "REG"]
    )
    if not all_events_for_3d:
        df.index = df.index.astype(int)

    graph_data_for_3d = disease_network_generator_for_3d.get_graph_data(df)

    file_utils.write_json(graph, output_file_for_graph)
    file_utils.write_json(graph_data_for_2d, output_file_for_2d)
    disease_network_generator_for_3d.save_graph(graph_data_for_3d, output_file_for_3d)

    ann_dir = os.path.dirname(output_file_for_graph)
    for doc_name, anns in doc_anns.items():
        file_utils.write_json(anns, os.path.join(ann_dir, doc_name + ".json"))

    generate_status(len(docs), len(docs), True, status_file)


if __name__ == "__main__":
    input_dir = "data/samples"
    output_dir = ".cache/samples"

    output_file_for_2d = os.path.join(output_dir, "2d_disease_network.json")
    output_file_for_3d = os.path.join(output_dir, "3d_disease_network.html")

    status_file = os.path.join(output_dir, "status.json")

    # docs = [
    #     (os.path.basename(input_file), file_utils.read_text(input_file))
    #     for input_file in glob(os.path.join(input_dir, "*.txt"))
    # ]

    import json
    docs = [((
        [
            ["T10001", "Disorder", [[0, 1]], "Sick", "Canonical Sick", "Sick Text"],
            ["T10002", "Positive_regulation", [[1, 2]], "Causing", "Canonical Causing", "caused"],
            ["T10003", "Positive_regulation", [[2, 3]], "Making", "Canonical Making", "made"],
            ["T10004", "Gene_expression", [[3, 4]], "Geck", "Canonical Geck", "geck"],
        ],
        [
            ["N10001", "Reference", "T10001", "DB", "WIG1", ""],
            ["N10002", "Reference", "T10002", "DB", "WIG2", ""],
            ["N10003", "Reference", "T10003", "DB", "WIG3", ""],
            ["N10004", "Reference", "T10004", "DB", "WIG4", ""],
        ],
        {
            "WIG1": "wig1",
            "WIG2": "wig2",
            "WIG3": "wig3",
            "WIG4": "wig4",
        },
        [
            ["T10001", "Disorder", [[0, 1]], "Sick", "Canonical Sick", "Sick Text"],
            ["T10002", "Positive_regulation", [[1, 2]], "Causing", "Canonical Causing", "caused"],
            ["T10003", "Positive_regulation", [[2, 3]], "Making", "Canonical Making", "made"],
            ["T10004", "Gene_expression", [[3, 4]], "Geck", "Canonical Geck", "geck"],
        ],
        [
            ["E1", "T10002", [["Theme", "E2"], ["Cause", "T10001"]]],
            ["E2", "T10003", [["Theme", "T10004"]]],
        ],
    ), "ABCD")]

    generate_graph_data(
        docs,
        output_file_for_graph,
        output_file_for_2d,
        output_file_for_3d,
        status_file,
    )
