# -*- coding: utf-8 -*-
# import json
# import logging
# import sys

# import requests

# logging.basicConfig(stream=sys.stdout, level=logging.INFO)
# logger = logging.getLogger(__name__)


# def annotate(task, doc):
#     try:
#         res = requests.post(
#             f"http://prm-ezcatdb.cbrc.jp/{task}/annotate", data={"text": doc}
#         )

#         res.raise_for_status()

#         annotations = res.json()

#         entities = annotations["entities"] + annotations["triggers"]
#         norms = annotations["normalizations"]
#         cuis = annotations["cui_data"]
#         events = annotations["events"]

#         return entities, norms, cuis, events
#     except requests.HTTPError as ex:
#         logger.exception(ex)

#     return [], [], {}, []


# def generate_network_input(doc):

#     el_entities, el_norms, el_cuis, _ = annotate("entity_linking", doc)
#     ev_entities, _, _, ev_events = annotate("event_extraction", doc)

#     norm_map = {}

#     entities = {e[0]: e for e in el_entities}

#     for norm in el_norms:
#         e = entities[norm[2]]
#         span_starts, span_ends = zip(*e[2])
#         span_start, span_end = min(span_starts), max(span_ends)

#         norm_map[span_start, span_end] = {
#             "id": norm[4],
#             "name": el_cuis[norm[4]],
#         }

#     entities = {e[0]: e for e in ev_entities}
#     events = {ev[0]: ev for ev in ev_events}

#     for e in entities.values():
#         span_starts, span_ends = zip(*e[2])
#         span_start, span_end = min(span_starts), max(span_ends)

#         norm = norm_map.get(
#             (span_start, span_end),
#             {
#                 "id": None,
#                 "name": None,
#             },
#         )

#         e.extend([doc[span_start:span_end], norm["name"], norm["id"]])

#     max_args = 0

#     rows = []

#     for ev in events.values():
#         max_args = max(max_args, len(ev[2]))

#         row = {
#             "corpus_name": "ipf_genes_20210127",
#             "article_id": "sample",
#             "event_id": ev[0],
#             "event_type": entities[ev[1]][1],
#             "trigger_id": ev[1],
#             "trigger_str": entities[ev[1]][3],
#             "trigger_canonical_name": entities[ev[1]][4],
#             "trigger_umls_id": entities[ev[1]][5],
#         }

#         for arg_index, (arg_role, arg_id) in enumerate(ev[2], start=1):
#             if arg_id.startswith("E"):
#                 arg_id = events[arg_id][1]

#             row[f"argument_id_{arg_index}"] = arg_id
#             row[f"argument_type_{arg_index}"] = entities[arg_id][1]
#             row[f"argument_str_{arg_index}"] = entities[arg_id][3]
#             row[f"argument_canonical_name_{arg_index}"] = entities[arg_id][4]
#             row[f"argument_umls_id_{arg_index}"] = entities[arg_id][5]
#             row[f"argument_role_type_{arg_index}"] = arg_role

#         rows.append(row)

#     logger.info("Max args: {}".format(max_args))

#     cols = [
#         "corpus_name",
#         "article_id",
#         "event_id",
#         "event_type",
#         "trigger_id",
#         "trigger_str",
#         "trigger_canonical_name",
#         "trigger_umls_id",
#     ]

#     for arg_index in range(1, max_args + 1):
#         cols.append(f"argument_id_{arg_index}")
#         cols.append(f"argument_type_{arg_index}")
#         cols.append(f"argument_str_{arg_index}")
#         cols.append(f"argument_canonical_name_{arg_index}")
#         cols.append(f"argument_umls_id_{arg_index}")
#         cols.append(f"argument_role_type_{arg_index}")

#     objs = []

#     for row in rows:
#         objs.append({col: row.get(col, None) for col in cols})

#     return objs


def mention_processor(api_input):
    all_unique_mentions = {}
    for item in api_input:
        """ In each row in the Statistics file needs at least two arguments """
        if item.get('argument_type_2') is not None:
            #if item['argument_type_2'] is not None and item['event_type'] == 'Positive_regulation' or item['event_type'] == 'Regulation':
            #if item['argument_type_2'] is not None and item['event_type'] == 'Regulation':
            #if item['argument_type_2'] is not None and item['event_type'] == 'Positive_regulation':
            try:
                #if item['argument_str_1'] not in all_unique_mentions and \
                #        item['event_type'] == 'Positive_regulation' or item['event_type'] == 'Regulation':

                if item['argument_str_1'] not in all_unique_mentions:
                    all_unique_mentions[item['argument_str_1']] = {'PMID': [], 'entity': [], 'event_type': [],
                                                                   'entity_type': [], 'role_type': [], 'canonical': [],
                                                                   'cui': [], 'target': {}}
                    all_unique_mentions[item['argument_str_1']]['PMID'].append(item['article_id'])
                    all_unique_mentions[item['argument_str_1']]['entity'].append(item['argument_str_1'])
                    all_unique_mentions[item['argument_str_1']]['entity_type'].append(item['argument_type_1'])
                    all_unique_mentions[item['argument_str_1']]['event_type'].append(item['event_type'])
                    if item['argument_role_type_1'][-1].isdigit():
                        all_unique_mentions[item['argument_str_1']]['role_type'].append(item['argument_role_type_1'][:-1])
                    else:
                        all_unique_mentions[item['argument_str_1']]['role_type'].append(item['argument_role_type_1'])
                    if item['argument_canonical_name_1'] is not None:
                        all_unique_mentions[item['argument_str_1']]['canonical'].append(item['argument_canonical_name_1'])
                    else:
                        all_unique_mentions[item['argument_str_1']]['canonical'].append('NA')
                    if item['argument_umls_id_1'] is not None:
                        all_unique_mentions[item['argument_str_1']]['cui'].append(item['argument_umls_id_1'])
                    else:
                        all_unique_mentions[item['argument_str_1']]['cui'].append('cui_less')
                    try:
                        if item['argument_str_2'] not in all_unique_mentions[item['argument_str_1']]['target']:
                            if item['argument_role_type_2'][-1].isdigit():
                                all_unique_mentions[item['argument_str_1']]['target'][item['argument_str_2']] = \
                                    item['argument_role_type_1'][:-1] + '→' + item['argument_role_type_2'][:-1]
                            else:
                                all_unique_mentions[item['argument_str_1']]['target'][item['argument_str_2']] = \
                                    item['argument_role_type_1'] + '→' + item['argument_role_type_2']
                    except Exception:
                        pass
                else:
                    try:
                        if item['argument_str_2'] not in all_unique_mentions[item['argument_str_1']]['target']:
                            if item['argument_role_type_2'][-1].isdigit():
                                all_unique_mentions[item['argument_str_1']]['target'][item['argument_str_2']] = \
                                    item['argument_role_type_1'][:-1] + '→' + item['argument_role_type_2'][:-1]
                            else:
                                all_unique_mentions[item['argument_str_1']]['target'][item['argument_str_2']] = \
                                    item['argument_role_type_1'] + '→' + item['argument_role_type_2']
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                #if item['argument_str_2'] not in all_unique_mentions and \
                #        item['event_type'] == 'Positive_regulation' or item['event_type'] == 'Regulation':
                if item['argument_str_2'] not in all_unique_mentions:
                    all_unique_mentions[item['argument_str_2']] = {'PMID': [], 'entity': [], 'event_type': [], 'entity_type': [],
                                                                   'role_type': [], 'canonical': [], 'cui': [],
                                                                   'target': {}}
                    all_unique_mentions[item['argument_str_2']]['PMID'].append(item['article_id'])
                    all_unique_mentions[item['argument_str_2']]['entity'].append(item['argument_str_2'])
                    all_unique_mentions[item['argument_str_2']]['entity_type'].append(item['argument_type_2'])
                    all_unique_mentions[item['argument_str_2']]['event_type'].append(item['event_type'])
                    if item['argument_role_type_2'][-1].isdigit():
                        all_unique_mentions[item['argument_str_2']]['role_type'].append(item['argument_role_type_2'][:-1])
                    else:
                        all_unique_mentions[item['argument_str_2']]['role_type'].append(item['argument_role_type_2'])
                    if item['argument_canonical_name_2'] is not None:
                        all_unique_mentions[item['argument_str_2']]['canonical'].append(item['argument_canonical_name_2'])
                    else:
                        all_unique_mentions[item['argument_str_2']]['canonical'].append('NA')
                    if item['argument_umls_id_2'] is not None:
                        all_unique_mentions[item['argument_str_2']]['cui'].append(item['argument_umls_id_2'])
                    else:
                        all_unique_mentions[item['argument_str_2']]['cui'].append('cui_less')
                    try:
                        if item['argument_str_3'] is not None:
                            if item['argument_str_3'] not in all_unique_mentions[item['argument_str_2']]['target']:
                                if item['argument_role_type_3'][-1].isdigit():
                                    all_unique_mentions[item['argument_str_2']]['target'][item['argument_str_3']] = \
                                        item['argument_role_type_2'][:-1] + '→' + item['argument_role_type_3'][:-1]
                                else:
                                    all_unique_mentions[item['argument_str_2']]['target'][item['argument_str_3']] = \
                                        item['argument_role_type_2'] + '→' + item['argument_role_type_3']
                    except Exception:
                        pass
                else:
                    try:
                        if item['argument_str_3'] is not None:
                            if item['argument_str_3'] not in all_unique_mentions[item['argument_str_2']]['target']:
                                if item['argument_role_type_3'][-1].isdigit():
                                    all_unique_mentions[item['argument_str_2']]['target'][item['argument_str_3']] = \
                                        item['argument_role_type_2'][:-1] + '→' + item['argument_role_type_3'][:-1]
                                else:
                                    all_unique_mentions[item['argument_str_2']]['target'][item['argument_str_3']] = \
                                        item['argument_role_type_2'] + '→' + item['argument_role_type_3']
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                #if item['argument_str_3'] not in all_unique_mentions and \
                #        item['event_type'] == 'Positive_regulation' or item['event_type'] == 'Regulation':
                if item['argument_str_3'] not in all_unique_mentions:
                    all_unique_mentions[item['argument_str_3']] = {'PMID': [], 'entity': [], 'event_type': [], 'entity_type': [],
                                                                   'role_type': [], 'canonical': [], 'cui': [],
                                                                   'target': {}}
                    all_unique_mentions[item['argument_str_3']]['PMID'].append(item['article_id'])
                    all_unique_mentions[item['argument_str_3']]['entity'].append(item['argument_str_2'])
                    all_unique_mentions[item['argument_str_3']]['entity_type'].append(item['argument_type_3'])
                    all_unique_mentions[item['argument_str_3']]['event_type'].append(item['event_type'])
                    if item['argument_role_type_3'][-1].isdigit():
                        all_unique_mentions[item['argument_str_3']]['role_type'].append(item['argument_role_type_3'][:-1])
                    else:
                        all_unique_mentions[item['argument_str_3']]['role_type'].append(item['argument_role_type_3'])
                    if item['argument_canonical_name_3'] is not None:
                        all_unique_mentions[item['argument_str_3']]['canonical'].append(item['argument_canonical_name_3'])
                    else:
                        all_unique_mentions[item['argument_str_3']]['canonical'].append('NA')
                    if item['argument_umls_id_3'] is not None:
                        all_unique_mentions[item['argument_str_3']]['cui'].append(item['argument_umls_id_3'])
                    else:
                        all_unique_mentions[item['argument_str_3']]['cui'].append('cui_less')
                    try:
                        if item['argument_str_4'] is not None:
                            if item['argument_str_4'] not in all_unique_mentions[item['argument_str_3']]['target']:
                                if item['argument_role_type_4'][-1].isdigit():
                                    all_unique_mentions[item['argument_str_3']]['target'][item['argument_str_4']] = \
                                        item['argument_role_type_3'][:-1] + '→' + item['argument_role_type_4'][:-1]
                                else:
                                    all_unique_mentions[item['argument_str_3']]['target'][item['argument_str_4']] = \
                                        item['argument_role_type_3'] + '→' + item['argument_role_type_4']
                    except Exception:
                        pass
                else:
                    try:
                        if item['argument_str_4'] is not None:
                            if item['argument_str_4'] not in all_unique_mentions[item['argument_str_3']]['target']:
                                if item['argument_role_type_4'][-1].isdigit():
                                    all_unique_mentions[item['argument_str_3']]['target'][item['argument_str_4']] = \
                                        item['argument_role_type_3'][:-1] + '→' + item['argument_role_type_4'][:-1]
                                else:
                                    all_unique_mentions[item['argument_str_3']]['target'][item['argument_str_4']] = \
                                        item['argument_role_type_3'] + '→' + item['argument_role_type_4']
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                #if item['argument_str_4'] not in all_unique_mentions and \
                #        item['event_type'] == 'Positive_regulation' or item['event_type'] == 'Regulation':
                if item['argument_str_4'] not in all_unique_mentions:
                    all_unique_mentions[item['argument_str_4']] = {'PMID': [], 'entity': [], 'event_type': [], 'entity_type': [],
                                                                   'role_type': [], 'canonical': [], 'cui': [],
                                                                   'target': {}}
                    all_unique_mentions[item['argument_str_4']]['PMID'].append(item['article_id'])
                    all_unique_mentions[item['argument_str_4']]['entity'].append(item['argument_str_4'])
                    all_unique_mentions[item['argument_str_4']]['entity_type'].append(item['argument_type_4'])
                    all_unique_mentions[item['argument_str_4']]['event_type'].append(item['event_type'])
                    if item['argument_role_type_4'][-1].isdigit():
                        all_unique_mentions[item['argument_str_4']]['role_type'].append(item['argument_role_type_4'][:-1])
                    else:
                        all_unique_mentions[item['argument_str_4']]['role_type'].append(item['argument_role_type_4'])
                    if item['argument_canonical_name_4'] is not None:
                        all_unique_mentions[item['argument_str_4']]['canonical'].append(item['argument_canonical_name_4'])
                    else:
                        all_unique_mentions[item['argument_str_4']]['canonical'].append('NA')
                    if item['argument_umls_id_4'] is not None:
                        all_unique_mentions[item['argument_str_4']]['cui'].append(item['argument_umls_id_4'])
                    else:
                        all_unique_mentions[item['argument_str_4']]['cui'].append('cui_less')
            except Exception:
                pass
    if None in all_unique_mentions: del all_unique_mentions[None]
    return all_unique_mentions


def graph_generation(all_unique_mentions, cluster_group, mention_types, graph_dict):
    for node_iter, (key, value) in enumerate(all_unique_mentions.items()):
        # if value["cui"][0] in cui_dict:
        #     generate_html_format(iter=node_iter, cui_dict=cui_dict, value=value)
        # else:
        #     generate_html_format_none(iter=node_iter, value=value)

        for i, (k, v) in enumerate(cluster_group.items()):
            if value["entity_type"][0] in v:
                layer_index = i

        url = "https://uts.nlm.nih.gov/uts/umls/searchResults?searchString=" + value["cui"][0]

        if value["cui"][0] == "cui_less":
            url = ""

        graph_dict["nodes"].append({
            "id": node_iter,
            "name": key,
            "PMID": value["PMID"][0],
            "entity_type": mention_types.index(value["entity_type"][0]),
            "entity_type_nominal": value["entity_type"][0],
            "event_type": value["event_type"][0],
            "role_type": value["role_type"][0],
            "cui": value["cui"][0],
            "canonical": value["canonical"][0],
            "mention": value["entity"][0],
            "type": layer_index,
            "size": len(value["target"]),
            "url": url
        })
        """ Explore All the Target Links for Current Node"""
        for it, val in value["target"].items():
            graph_dict["links"].append({
                "source": node_iter,
                "target": list(all_unique_mentions).index(it),
                "label": val
            })
    return graph_dict


# def generate_html_format(iter, cui_dict, value):
#     path = "./html_dump/"
#     filename = path + str(iter) + '.' + 'html'
#     items = json.loads(cui_dict[value["cui"][0]])
#     with open(filename, 'w') as fout:
#         fout.write("<!DOCTYPE html>\n")
#         fout.write("<html>\n")
#         fout.write("<head>\n")
#         fout.write("<style>")
#         fout.write("h1 {text-align: center;}\n")
#         fout.write(".tab { margin-left: 20px; }\n")
#         fout.write("</style>\n")
#         fout.write("</head>\n")
#         fout.write("<body>\n")
#         fout.write("<h1 style='color:blue'>{}</h1>\n".format(value["entity"][0]))
#         fout.write("<h4 class='tab'>Canonical Name</h4>\n")
#         fout.write("<p class='tab'>{}</p>\n".format(items["cui_name"]))
#         fout.write("<h4 class='tab'>Concept Unique Identifier (CUI)</h4>\n")
#         fout.write("<p class='tab'>{}</p>\n".format(value["cui"][0]))
#         fout.write("<h4 class='tab'>Definition</h4>\n")
#         if items["definitions"] != 'NONE':
#             for item in items["definitions"]:
#                 for k, defn in item.items():
#                     fout.write("<p class='tab'>{}: {}</p>\n".format(k, ' '.join(defn)))
#         else:
#             fout.write("<p class='tab'>NONE</p>\n")
#         fout.write("<h4 class='tab'>Semantic Definition</h4>\n".format())
#         fout.write("<p class='tab'>{}</p>\n".format(' '.join(items["sem_defination"])))
#         fout.write("<h4 class='tab'>Semantic Type</h4>\n")
#         fout.write("<p class='tab'>{}</p>\n".format(items["sem_type"]))
#         fout.write("<h4 class='tab'>Semantic Type Name</h4>\n")
#         fout.write("<ui class='list'>\n")
#         for item in items["semanticTypes_name"]:
#             fout.write("<li class='tab'>{}</li>\n".format(item))
#         fout.write("</ui>\n")
#         fout.write("<h4 class='tab'>Alias</h4>\n")
#         fout.write("<ui class='list'>\n")
#         for dict in items["atoms"]:
#             fout.write("<li class='tab'>{} [rootSource: {}, code: {}, aui: {}]</li>\n".format(
#                 dict['atom_name'], dict['rootSource'], dict['cui_code'], dict['aui']))
#         fout.write("</ui>\n")
#         fout.write("</body>\n")
#         fout.write("</html>\n")


# def generate_html_format_none(iter, value):
#     path = "./html_dump/"
#     filename = path + str(iter) + '.' + 'html'
#     with open(filename, 'w') as fout:
#         fout.write("<!DOCTYPE html>\n")
#         fout.write("<html>\n")
#         fout.write("<head>\n")
#         fout.write("<style>")
#         fout.write("h1 {text-align: center;}\n")
#         fout.write(".tab { margin-left: 20px; }\n")
#         fout.write("</style>\n")
#         fout.write("</head>\n")
#         fout.write("<body>\n")
#         fout.write("<h1 style='color:blue'>{}</h1>\n".format(value["entity"][0]))
#         fout.write("<h4 class='tab'>Canonical Name</h4>\n")
#         if value["canonical"][0] != "":
#             fout.write("<p class='tab'>{}</p>\n".format(value["canonical"][0]))
#         else:
#             fout.write("<p class='tab'>{}</p>\n".format("NA"))
#         if value["cui"][0] != "":
#             fout.write("<h4 class='tab'>Concept Unique Identifier (CUI)</h4>\n")
#             fout.write("<p class='tab'>{}</p>\n".format(value["cui"][0]))
#         fout.write("</body>\n")
#         fout.write("</html>\n")


def get_graph_data(all_events):
    graph_dict = {"nodes": [], "links": [], "directed": True}
    cluster_group = {
        'Phenotype': ['Disorder', 'Measurement', 'Entity_Property'],
        'Organ': ['Anatomical_entity'],
        'Cell': ['Cell'],
        'Organelle': ['Cell_component'],
        'Molecule': ['GGPs', 'Organic_compound_other', 'Inorganic_compound', 'Pharmacological_substance',
                     'Amino_acid_monomer', 'MENTION'],
        'other': ['Gene_expression', 'Localization', 'Biological_process', 'Molecular_function', 'Cellular_process',
                  'Positive_regulation', 'Regulation', 'Negative_regulation', 'Pathway', 'Speculation_cue',
                  'Negation_cue', 'Method_cue', 'Subject', 'Conversion', 'Artificial_process']
    }
    mention_types = [item for k, v in cluster_group.items() for item in v]

    all_unique_mentions = mention_processor(api_input=all_events)
    graph_dict = graph_generation(all_unique_mentions=all_unique_mentions,
                                  cluster_group=cluster_group,
                                  mention_types=mention_types,
                                  graph_dict=graph_dict)

    return graph_dict
