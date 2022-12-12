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



REGULATION_EVENT_TYPES = {"Positive_regulation", "Negative_regulation"}
POSITIVE_REGULATION = "Positive_regulation"
NEGATIVE_REGULATION = "Negative_regulation"
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


def collapse_regulation(entities_nt, events_nt):
    # make editable, otherwise this becomes very complicated
    entities = { k: SimpleNamespace(**v._asdict()) for k, v in entities_nt.items() }
    events = { k: SimpleNamespace(**v._asdict()) for k, v in events_nt.items() }

    regulation_evids = {evid for evid, ev in events.items() if ev.regulation != Regulation.UNREGULATED}
    subid_count = 0

    idmap = {}
    maxids = {
        'E': max(int(key[1:]) for key in events.keys()) if events else 0,
        'T': max(int(key[1:]) for key in entities.keys()) if entities else 0,
    }


    def new_id(oldid, oldtype=None):
        key = (oldid, oldtype)
        newid = idmap.get(key)
        if not newid:
            kind = oldid[0]
            maxids[kind] += 1
            newid = f"{kind}{maxids[kind]}"
        return newid

    def replace_id(item, newid):
        for ev in events.values():
            if ev.trigger == item.id:
                ev.trigger = newid
            newargs = []
            for arg in ev.args:
                if arg[1] == item.id:
                    arg = [arg[0], newid]
                newargs.append(arg)
            ev.args = newargs

    def calc_regulation(reg1, reg2):
        return Regulation((reg1 or Regulation.POSITIVE) * (reg2 or Regulation.POSITIVE))

    solved = True
    while solved:
        solved = set()
        for evid in regulation_evids:
            ev = events[evid]
            if ev.regulation is None:
                # Solved and deleted
                continue

            trigger = entities[ev.trigger]
            consequent_id = next((a[1] for a in events[evid].args if a[0] == "Theme"), None)
            if not consequent_id:
                # solved already
                continue

            # Is it a direct regulation?
            consequent_en = entities.get(consequent_id)
            if consequent_en:
                trigger.type = DIRECT
                solved.add(evid)
                continue

            consequent_ev = events.get(consequent_id)
            # Regulation event must have a consequent event
            if not consequent_ev:
                continue

            antecedent_arg = next((a for a in ev.args if a[0] in ['Cause', 'disorder']), None) # check error?
            if antecedent_arg:
                antecedent_ev = events.get(antecedent_arg[1], None)
                if antecedent_ev and not antecedent_ev.regulation:
                    # The only causes to a regulation event can be entities or other regulation events
                    solved.add(evid)
                    continue
            new_regulation = calc_regulation(ev.regulation, consequent_ev.regulation)

            evtype = entities[consequent_ev.trigger].type
            if evtype in { POSITIVE_REGULATION, NEGATIVE_REGULATION }:
                # Don't combine these yet; wait till they get processed first
                continue

            newid = new_id(consequent_id)
            new_args = [[*arg] for arg in consequent_ev.args if arg[0] not in ['Cause', 'disorder']]
            if antecedent_arg:
                new_args.append([*antecedent_arg])
            new_consequent_ev = SimpleNamespace(**consequent_ev.__dict__)
            new_consequent_ev.id = newid
            new_consequent_ev.args = new_args
            new_consequent_ev.regulation = new_regulation
            events[newid] = new_consequent_ev
            # Mark as "deleted"
            ev.regulation = None
            # XXX does not work with multiple references; should copy or something
            replace_id(ev, newid)

            solved.add(evid)
            continue

        regulation_evids -= solved

    for evid in list(events.keys()):
        if entities[events[evid].trigger].type in [POSITIVE_REGULATION, NEGATIVE_REGULATION]:
            del events[evid]

    entities = { enid: ENTITY(**en.__dict__) for enid, en in entities.items() }
    events = { evid: EVENT(**ev.__dict__) for evid, ev in events.items() }
    return entities, events


def generate_status(doc_idx, num_docs, status, status_file):
    file_utils.write_json(
        {"current": doc_idx, "total": num_docs, "status": status}, status_file
    )


def add_to_graph(doc_name, c_entities, c_events, nodes, edges, nodelist):
    def make_entity_node(entity):
        node_name = entity.canonical_name or f'"{entity.text}"'
        node_key = (node_name, entity.umls_id)
        node = nodes.get(node_key)
        if not node:
            node = {
                "id": len(nodelist),
                "name": node_name,
                "type": entity.type,
                "cui": entity.umls_id,
                "url": entity.umls_id and "https://uts.nlm.nih.gov/uts/umls/searchResults?searchString=" + entity.umls_id,
                "brat_ids": [[entity.id]],
                "count": 0,
                "documents": [],
            }
            nodelist.append(node)
            nodes[node_key] = node
        node["count"] += 1
        return node["id"]

    def make_event_edge(ev, trigger, cause_no, theme_no):
        edge_key = (cause_no, theme_no)
        edge = edges.get(edge_key)
        if not edge:
            edge = {
                "source": cause_no,
                "target": theme_no,
                "type": trigger.type,
                "instances": [],
                "documents": [],
            }
            edges[edge_key] = edge

            # see if there is an edge going the other way
            rev_edge_key = (theme_no, cause_no)
            rev_edge = edges.get(rev_edge_key)
            if rev_edge:
                edge["bidir"] = 0
                rev_edge["bidir"] = 1

        edge["instances"].append({
            "type": trigger.type, 
            "regulation": ev.regulation,
            "doc": doc_name,
            "brat_ids": [[ev.trigger]], # add all involved IDs?
        })
        return edge_key

    node_no_set = set()
    edge_key_set = set()
    for ev in c_events.values():
        if not ev.regulation:
            continue
        cause_role, cause = next((a for a in ev.args if a[0] in {'Cause', 'disorder'}), (None, None))
        if not cause:
            continue
        if cause in c_events:
            continue
        theme_role, theme = next((a for a in ev.args if a[0] == 'Theme'), (None, None))
        if not theme:
            continue
        if theme in c_events:
            continue

        trigger = c_entities[ev.trigger]
        cause = c_entities[cause]
        theme = c_entities[theme]
        cause_name = cause.canonical_name or f'"{cause.text}"'
        theme_name = theme.canonical_name or f'"{theme.text}"'
        # reg = {
        #         Regulation.POSITIVE: 'POS',
        #         Regulation.NEGATIVE: 'NEG',
        # }.get(ev.regulation)

        cause_no = make_entity_node(cause)
        theme_no = make_entity_node(theme)
        edge_key = make_event_edge(ev, trigger, cause_no, theme_no)

        node_no_set.add(cause_no)
        node_no_set.add(theme_no)
        edge_key_set.add(edge_key)

    key = lambda e: sorted([e["source"], e["target"]])
    edgelist = sorted(edges.values(), key=key)
    for pair, group in itertools.groupby(edgelist, key=key):
        group = list(group)
        link_count = len(group)
        for link_no, e in enumerate(group):
            e["link_count"] = link_count
            e["reverse_link"] = e["source"] > e["target"]
            e["link_no"] = link_no

    for node_no in node_no_set:
        nodelist[node_no]["documents"].append(doc_name)
    for edge_key in edge_key_set:
        edges[edge_key]["documents"].append(doc_name)

    return {
        "nodes": nodelist,
        "links": list(edges.values()),
    }


def generate_graph_data(
    docs,
    output_file_for_graph,
    output_file_for_2d,
    output_file_for_3d,
    status_file,
):
    max_args = 0
    all_events = []

    nodes = {}
    edges = {}
    nodelist = []
    doc_anns = {}

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

        # c_entities, c_events = collapse_regulation(entities, events)
        # XXX GTDEBUG
        from pprint import pprint
        print("---ORIGINAL ENTITIES")
        pprint(entities)
        print("---ORIGINAL EVENTS")
        pprint(events)

        c_entities, c_events = collapse_regulation(entities, events)
        # XXX GTDEBUG
        from pprint import pprint
        print("---COLLAPSED ENTITIES")
        pprint(c_entities)
        print("---COLLAPSED EVENTS")
        pprint(c_events)

        add_to_graph(doc_name, c_entities, c_events, nodes, edges, nodelist)

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

    graph = {
        "nodes": nodelist,
        "links": list(edges.values()),
    }
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
