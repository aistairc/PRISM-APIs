# -*- coding: utf-8 -*-
import os

from flask import Blueprint, render_template, request
from sqlitedict import SqliteDict
from tqdm import tqdm
from utils import file_utils

from .config import config, samples
from .visual_conf import parse_visual_conf


def get_namedb(namedb_path, kb_path):
    if not os.path.exists(namedb_path):
        namedb = SqliteDict(filename=namedb_path, flag="n")

        for concept in tqdm(file_utils.read_json_lines(kb_path), desc="Processing KB"):
            namedb[concept["id"]] = concept["name"]

        namedb.commit()

    return SqliteDict(filename=namedb_path, flag="r")


def get_cui_data(cuis):
    return {cui: namedb[cui] for cui in cuis}


namedb = get_namedb(config["umls_name_sqlite"], config["umls_kb"])


def get_doc_data(text, model):
    doc, sentence_standoffs, token_standoffs = model(text)

    entity_doc_data = [[ann.id, ann.type, ann.spans] for ann in doc.get_entities()]
    normalization_doc_data = [
        [ann.id, ann.type, ann.target, ann.refdb, ann.refid, ann.tail]
        for ann in doc.get_normalizations()
    ]
    event_doc_data = [[ann.id, ann.trigger, ann.args] for ann in doc.get_events()]
    trigger_doc_data = [[ann.id, ann.type, ann.spans] for ann in doc.get_triggers()]
    relation_doc_data = [
        [ann.id, ann.type, [(ann.arg1l, ann.arg1), (ann.arg2l, ann.arg2)]]
        for ann in doc.get_relations()
    ]
    attribute_doc_data = [
        [ann.id, ann.type, ann.target, ann.value] for ann in doc.get_attributes()
    ]
    norm_cuis = [norm[4] for norm in normalization_doc_data if norm[3] == "UMLS"]
    cui_data = get_cui_data(norm_cuis)
    doc_data = {
        "entities": entity_doc_data,
        "events": event_doc_data,
        "relations": relation_doc_data,
        "triggers": trigger_doc_data,
        "modifications": [],
        "attributes": attribute_doc_data,
        "equivs": [],
        "normalizations": normalization_doc_data,
        "cui_data": cui_data,
        "comments": [],
        "text": text,
        "annfile": str(doc),
        "token_offsets": token_standoffs,
        "sentence_offsets": sentence_standoffs,
        # "mtime": 1533538148.3611436,
        # "ctime": 1585644597.360524,
        # "source_files": [
        #     "ann",
        #     "txt"
        # ],
        # "action": "getDocument",
        # "protocol": 1,
        # "messages": []
    }

    return doc_data


def get_coll_data(visual_conf):
    norm_coll_data = [
        # [
        #     "UMLS",
        #     "https://www.nlm.nih.gov/research/umls/",
        #     "https://uts.nlm.nih.gov//metathesaurus.html?cui=%s",
        #     None,
        #     True
        # ]
    ]
    event_coll_data = [
        # {
        #     "name": "Catalysis",
        #     "type": "Catalysis",
        #     "unused": False,
        #     "labels": [
        #         "Catalysis",
        #     ],
        #     "attributes": [
        #     ],
        #     "normalizations": [],
        #     "fgColor": "black",
        #     "bgColor": "#e0ff00",
        #     "borderColor": "darken",
        #     # "hotkey": "C",
        #     "arcs": [
        #         {
        #             "type": "Theme",
        #             "labels": [
        #                 "Theme",
        #                 "Th"
        #             ],
        #             "hotkey": "T",
        #             "color": "black",
        #             "arrowHead": "triangle,5",
        #             "targets": [
        #                 "Catalysis",
        #                 "DNA_methylation",
        #                 "DNA_demethylation",
        #                 "Acetylation",
        #                 "Methylation",
        #                 "Glycosylation",
        #                 "Hydroxylation",
        #                 "Phosphorylation",
        #                 "Ubiquitination",
        #                 "Deacetylation",
        #                 "Demethylation",
        #                 "Deglycosylation",
        #                 "Dehydroxylation",
        #                 "Dephosphorylation",
        #                 "Deubiquitination"
        #             ]
        #         },
        #         {
        #             "type": "Cause",
        #             "labels": [
        #                 "Cause",
        #                 "Ca"
        #             ],
        #             "color": "#007700",
        #             "arrowHead": "triangle,5",
        #             "targets": [
        #                 "Protein"
        #             ]
        #         }
        #     ],
        #     "children": []
        # }
    ]
    entity_coll_data = [
        {
            "name": tag,
            "type": tag,
            "unused": False,
            "labels": description.get("labels", [tag]),
            "attributes": [],
            "normalizations": [],
            "fgColor": description.get("fgColor", "black"),
            "bgColor": description.get("bgColor", "white"),
            "borderColor": description.get("borderColor", "darken"),
            # "hotkey": "A-C-S-T",
            "arcs": [
                # {
                #     "type": "Equiv",
                #     "labels": [
                #         "Equiv",
                #         "Eq"
                #     ],
                #     "color": "black",
                #     "dashArray": "3,3",
                #     "arrowHead": "none",
                #     "targets": [
                #         "Protein"
                #     ]
                # }
            ],
            "children": [],
        }
        for tag, description in visual_conf.items()
    ]
    rel_coll_data = [
        # {
        #     "name": "Equiv",
        #     "type": "Equiv",
        #     "unused": False,
        #     "labels": [
        #         "Equiv",
        #         "Eq"
        #     ],
        #     "attributes": [],
        #     "properties": {
        #         "symmetric": True,
        #         "transitive": True
        #     },
        #     "color": "black",
        #     "dashArray": "3,3",
        #     "arrowHead": "none",
        #     "args": [
        #         {
        #             "role": "Arg1",
        #             "targets": [
        #                 "Protein"
        #             ]
        #         },
        #         {
        #             "role": "Arg2",
        #             "targets": [
        #                 "Protein"
        #             ]
        #         }
        #     ],
        #     "children": []
        # },
        # {
        #     "name": "Equiv",
        #     "type": "Equiv",
        #     "unused": False,
        #     "labels": [
        #         "Equiv",
        #         "Eq"
        #     ],
        #     "attributes": [],
        #     "properties": {
        #         "symmetric": True,
        #         "transitive": True
        #     },
        #     "color": "black",
        #     "dashArray": "3,3",
        #     "arrowHead": "none",
        #     "args": [
        #         {
        #             "role": "Arg1",
        #             "targets": [
        #                 "Entity"
        #             ]
        #         },
        #         {
        #             "role": "Arg2",
        #             "targets": [
        #                 "Entity"
        #             ]
        #         }
        #     ],
        #     "children": []
        # }
    ]
    event_attr_coll_data = [
        # {
        #     "name": "Negation",
        #     "type": "Negation",
        #     "unused": False,
        #     "labels": None,
        #     "values": [
        #         {
        #             "name": "Negation",
        #             "box": "crossed"
        #         }
        #     ]
        # },
        # {
        #     "name": "Speculation",
        #     "type": "Speculation",
        #     "unused": False,
        #     "labels": None,
        #     "values": [
        #         {
        #             "name": "Speculation",
        #             "dashArray": "3,3"
        #         }
        #     ]
        # }
    ]
    unconf_coll_data = [
        # {
        #     "name": "Person",
        #     "type": "Person",
        #     "unused": True,
        #     "labels": [
        #         "Person"
        #     ],
        #     "fgColor": "black",
        #     "bgColor": "#ffccaa",
        #     "borderColor": "darken",
        #     "color": "black",
        #     "arrowHead": "triangle,5"
        # }
    ]
    coll_data = {
        # "items": [],
        # "header": [],
        # "parent": "T_2011",
        # "messages": [],
        # "description": "",
        # "search_config": [],
        # "disambiguator_config": [],
        # "normalization_config": norm_coll_data,
        # "annotation_logging": False,
        # "ner_taggers": [],
        "event_types": event_coll_data,
        "entity_types": entity_coll_data,
        "relation_types": rel_coll_data,
        "event_attribute_types": event_attr_coll_data,
        "relation_attribute_types": [],
        "entity_attribute_types": [],
        "unconfigured_types": unconf_coll_data,
        "ui_names": {
            "entities": "entities",
            "relations": "relations",
            "events": "events",
            "attributes": "attributes",
        },
        "visual_options": {"arc_bundle": "all", "text_direction": "ltr"},
        # "action": "getCollectionInformation",
        # "protocol": 1
    }

    return coll_data


def make_frontend(frontend_name, model):
    visual_conf, visual_conf_defaults = parse_visual_conf(config["visual_conf_path"])

    frontend = Blueprint(frontend_name, __name__, static_folder="static")

    @frontend.route("/")
    def index():
        coll_data = get_coll_data(visual_conf)
        return render_template(
            "index.html",
            coll_data=coll_data,
            samples=samples,
            app_name=frontend_name,
        )

    @frontend.route("/annotate", methods=["POST"])
    def annotate():
        text = request.form["text"]
        try:
            data = get_doc_data(text, model)
        except x:
            logger.exception(x)
            raise
        return data

    return frontend
