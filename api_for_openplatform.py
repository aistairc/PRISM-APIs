# -*- coding: utf-8 -*-
# import itertools
# import json
import os
import socket

# import tempfile
from dataclasses import asdict
from typing import List, Optional

import fastapi

# import pandas as pd
import regex
import requests
import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from loguru import logger
from pydantic import Field, parse_obj_as
from pydantic.dataclasses import dataclass

# import disease_network_generator_for_2d
# import disease_network_generator_for_3d
# from utils import file_utils

EXTERNAL_API_BASE_URL = os.environ.get('EXTERNAL_API_BASE_URL', 'http://127.0.0.1:9091')

# LOG_FILE = "logs/api_for_openplatform.log"

# file_utils.make_dirs(os.path.dirname(LOG_FILE))

# logger.add(LOG_FILE)

URL_PREFIX = "/api-for-openplatform"

EMAIL_PATTERN = regex.compile(r"^[\w\.-]+@[\w\.-]+$", flags=regex.IGNORECASE)

main_description = """
### General API Information

This is an interactive API documentation where you can find all
the information about our API's endpoints including the description
of each endpoint, what data structure is expected in a request,
what is returned in the response as well as examples for experimenting
with our APIs.
In each API explanation box, we also provide a try-it-out button
so you can try the API directly on the documentation.
Moreover, you can also modify the default input examples when testing
or click on the schema button to understand more about the data structure
required by the API.

### Supported NLP models

Currently, we are providing access to our 2 published NLP models:

- **Named Entity Recognition**
[Demo](http://prm-ezcatdb.cbrc.jp/named_entity_recognition)
- **Entity Linking**
[Demo](http://prm-ezcatdb.cbrc.jp/entity_linking)

For more code examples of how to use our APIs,
please visit our GitHub repository at this link
[https://github.com/aistairc/kirt-api-docs](https://github.com/aistairc/kirt-api-docs).

---
Knowledge and Information Research Team (KIRT)<br/>
Artificial Intelligence Research Center (AIRC)<br/>
National Institute of Advanced Industrial Science and Technology (AIST)
"""

app = FastAPI(
    title="API Documentation",
    description=main_description,
    version="1.0.0",
    license_info={
        "name": "Apache 2.0",
        "url": "http://www.apache.org/licenses/LICENSE-2.0",
    },
    openapi_url=f"{URL_PREFIX}/openapi.json",
    docs_url=f"{URL_PREFIX}",
    redoc_url=None,
)


@dataclass
class Span:
    start: int = Field(
        ..., title="The index of the first character of the span in the document"
    )
    end: int = Field(
        ..., title="The index of the first character after the span in the document"
    )


@dataclass
class Entity:
    id: str = Field(..., title="The ID of the predicted entity")
    type: str = Field(..., title="The entity type of the predicted entity")
    span: Span = Field(
        ..., title="The position of the predicted entity in the document"
    )
    text: str = Field(..., title="The mention text of the predicted entity")


@dataclass
class LinkedEntity(Entity):
    concept_id: Optional[str] = Field(
        None, title="The UMLS concept ID linked to the predicted entity mention"
    )
    concept_name: Optional[str] = Field(
        None, title="The UMLS canonical name corresponding to the UMLS concept ID"
    )


# @dataclass
# class Relation:
#     id: str = Field(..., title="The ID of the predicted relation")
#     type: str = Field(..., title="The relation type of the predicted relation")
#     left_arg_id: str = Field(
#         ...,
#         title="The entity ID serving as the left argument of the predicted relation",
#     )
#     right_arg_id: str = Field(
#         ...,
#         title="The entity ID serving as the right argument of the predicted relation",
#     )


# @dataclass
# class EventArgument:
#     arg_role: str = Field(..., title="The role of the argument")
#     arg_id: str = Field(..., title="The entity or event ID serving as the argument")


# @dataclass
# class Modality:
#     id: str = Field(..., title="The ID of the predicted modality")
#     type: str = Field(..., title="The modality type of the predicted modality")


# @dataclass
# class Event:
#     id: str = Field(..., title="The ID of the predicted event")
#     trigger_id: str = Field(..., title="The trigger ID of the predicted event")
#     args: List[EventArgument] = Field(
#         ..., title="The list of arguments of the predicted event"
#     )
#     modalities: List[Modality] = Field(
#         [], title="The list of modalities of the predicted event"
#     )


@dataclass
class Doc:
    text: str = Field(..., title="The text of the document")


@dataclass
class AnnotatedDoc(Doc):
    token_boundaries: List[Span] = Field(
        ...,
        title="The list of token boundaries for extracting tokens from the document",
    )
    sentence_boundaries: List[Span] = Field(
        ...,
        title="The list of sentence boundaries for extracting "
        "sentences from the document",
    )


@dataclass
class NamedEntityRecognitionData(AnnotatedDoc):
    entities: List[Entity] = Field(..., title="The list of predicted entities")


# @dataclass
# class RelationExtractionData(NamedEntityRecognitionData):
#     relations: List[Relation] = Field(..., title="The list of predicted relations")


# @dataclass
# class EventExtractionData(NamedEntityRecognitionData):
#     events: List[Event] = Field(..., title="The list of predicted events")


@dataclass
class EntityLinkingData(NamedEntityRecognitionData):
    entities: List[LinkedEntity] = Field(
        ..., title="The list of predicted entity mentions linked to UMLS concepts"
    )


# @dataclass
# class DiseaseNetworkDoc:
#     entities: List[Entity] = Field(
#         ...,
#         title="The list of predicted entities from the event extraction model",
#         example=[
#             {
#                 "id": "T10001",
#                 "type": "Cell",
#                 "span": {"start": 9, "end": 19},
#                 "text": "A549 cells",
#             },
#             {
#                 "id": "T10004",
#                 "type": "GGPs",
#                 "span": {"start": 75, "end": 84},
#                 "text": "TGF-beta1",
#             },
#             {
#                 "id": "T10002",
#                 "type": "Cellular_process",
#                 "span": {"start": 50, "end": 53},
#                 "text": "EMT",
#             },
#             {
#                 "id": "T10003",
#                 "type": "Artificial_process",
#                 "span": {"start": 60, "end": 69},
#                 "text": "treatment",
#             },
#         ],
#     )
#     events: List[Event] = Field(
#         ...,
#         title="The list of predicted events from the event extraction model",
#         example=[
#             {
#                 "id": "E1",
#                 "trigger_id": "T10002",
#                 "args": [{"arg_role": "Theme", "arg_id": "T10001"}],
#                 "modalities": [],
#             },
#             {
#                 "id": "E2",
#                 "trigger_id": "T10003",
#                 "args": [
#                     {"arg_role": "Theme", "arg_id": "T10001"},
#                     {"arg_role": "Instrument", "arg_id": "T10004"},
#                 ],
#                 "modalities": [],
#             },
#         ],
#     )
#     linked_entities: List[LinkedEntity] = Field(
#         ...,
#         title="The list of predicted entities from the entity linking model",
#         example=[
#             {
#                 "id": "T1",
#                 "type": "Cell",
#                 "span": {"start": 9, "end": 19},
#                 "text": "A549 cells",
#                 "concept_id": "C4277577",
#                 "concept_name": "A549 Cells",
#             },
#             {
#                 "id": "T2",
#                 "type": "Cellular_process",
#                 "span": {"start": 50, "end": 53},
#                 "text": "EMT",
#                 "concept_id": None,
#                 "concept_name": None,
#             },
#             {
#                 "id": "T3",
#                 "type": "Artificial_process",
#                 "span": {"start": 60, "end": 69},
#                 "text": "treatment",
#                 "concept_id": None,
#                 "concept_name": None,
#             },
#             {
#                 "id": "T4",
#                 "type": "GGPs",
#                 "span": {"start": 75, "end": 84},
#                 "text": "TGF-beta1",
#                 "concept_id": "C1704256",
#                 "concept_name": "Transforming Growth Factor Beta 1",
#             },
#         ],
#     )


# @dataclass
# class DiseaseNetworkData:
#     graph_data: List[dict] = Field(
#         ..., title="The graph data generated for the 2D and 3D Disease Network"
#     )
#     visualization_2d: Optional[str] = Field(
#         None, title="The 2D Disease Network visualization of the graph data"
#     )
#     visualization_3d: Optional[str] = Field(
#         None, title="The 3D Disease Network visualization of the graph data"
#     )


@dataclass
class StatusData:
    status: str = Field(
        ..., title="The current status of the API server", example="Running"
    )


def verify_email(email):
    return EMAIL_PATTERN.fullmatch(email)


def annotate_doc(doc, task):
    task = {
        "ner": "named_entity_recognition",
        # "re": "relation_extraction",
        # "ee": "event_extraction",
        "el": "entity_linking",
    }[task]

    response = requests.post(
        f"{EXTERNAL_API_BASE_URL}/{task}/annotate", data={"text": doc.text}
    )

    response.raise_for_status()

    annotations = response.json()

    doc = annotations["text"]

    entities = []

    for entity_id, entity_type, entity_spans in (
        annotations["entities"] + annotations["triggers"]
    ):
        entity_starts, entity_ends = zip(*entity_spans)

        entity_span = Span(min(entity_starts), max(entity_ends))

        entities.append(
            LinkedEntity(
                entity_id,
                entity_type,
                entity_span,
                doc[entity_span.start : entity_span.end],
            )
        )

    id_entities = {entity.id: entity for entity in entities}

    for _, _, entity_id, _, concept_id, _ in annotations["normalizations"]:
        entity = id_entities[entity_id]

        entity.concept_id = concept_id
        entity.concept_name = annotations["cui_data"][concept_id]

    # relations = []

    # for (
    #     relation_id,
    #     relation_type,
    #     ((_, relation_left_arg_id), (_, relation_right_arg_id)),
    # ) in annotations["relations"]:
    #     relations.append(
    #         Relation(
    #             relation_id, relation_type, relation_left_arg_id, relation_right_arg_id
    #         )
    #     )

    # events = parse_obj_as(List[Event], annotations["events"])

    # id_events = {event.id: event for event in events}

    # for attribute_id, attribute_type, attribute_target, _ in annotations["attributes"]:
    #     id_events[attribute_target].modalities.append(
    #         Modality(attribute_id, attribute_type)
    #     )

    return {
        "text": doc,
        "entities": entities,
        # "relations": relations,
        # "events": events,
        "token_boundaries": parse_obj_as(List[Span], annotations["token_offsets"]),
        "sentence_boundaries": parse_obj_as(
            List[Span], annotations["sentence_offsets"]
        ),
    }


@app.get(
    f"{URL_PREFIX}/status",
    response_model=StatusData,
    tags=["Status"],
    summary="Check API server status",
    description="Use this to check the current status of the API server",
    response_description="Status OK",
)
def status():
    return StatusData("Running")


@app.post(
    f"{URL_PREFIX}/named_entity_recognition",
    response_model=NamedEntityRecognitionData,
    tags=["Models"],
    summary="Named Entity Recognition Model",
    description="Use this model to extract named entities from a given document",
    response_description="Return the list of predicted entities",
)
def named_entity_recognition(
    email: str = Query(
        ..., description="Your email address", example="example@domain.com"
    ),
    doc: Doc = Body(
        ...,
        description="The document that needs to be annotated",
        example=asdict(
            Doc(
                "BACKGROUND: Fibroblastic foci are characteristic features in "
                "lung parenchyma of patients with idiopathic pulmonary fibrosis (IPF)."
            )
        ),
    ),
):
    logger.info("User: {}", email)

    if not verify_email(email):
        raise HTTPException(fastapi.status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    return annotate_doc(doc, "ner")


# @app.post(
#     f"{URL_PREFIX}/relation_extraction",
#     response_model=RelationExtractionData,
#     tags=["Models"],
#     summary="Relation Extraction Model",
#     description="Use this model to extract named entities and relations "
#     "from a given document",
#     response_description="Return the list of predicted entities and relations",
# )
# def relation_extraction(
#     email: str = Query(
#         ..., description="Your email address", example="example@domain.com"
#     ),
#     doc: Doc = Body(
#         ...,
#         description="The document that needs to be annotated",
#         example=asdict(
#             Doc(
#                 "BACKGROUND: Fibroblastic foci are characteristic features in "
#                 "lung parenchyma of patients with idiopathic pulmonary fibrosis (IPF)."
#             )
#         ),
#     ),
# ):
#     logger.info("User: {}", email)

#     if not verify_email(email):
#         raise HTTPException(fastapi.status.HTTP_401_UNAUTHORIZED, "Not authenticated")

#     return annotate_doc(doc, "re")


# @app.post(
#     f"{URL_PREFIX}/event_extraction",
#     response_model=EventExtractionData,
#     tags=["Models"],
#     summary="Event Extraction Model",
#     description="Use this model to extract named entities and events "
#     "from a given document",
#     response_description="Return the list of predicted entities and events",
# )
# def event_extraction(
#     email: str = Query(
#         ..., description="Your email address", example="example@domain.com"
#     ),
#     doc: Doc = Body(
#         ...,
#         description="The document that needs to be annotated",
#         example=asdict(
#             Doc(
#                 "While most sources agree that IPF does not result from "
#                 "a primary immunopathogenic mechanism, evidence gleaned from "
#                 "animal modeling and human studies suggests that innate and "
#                 "adaptive immune processes can orchestrate existing fibrotic responses."
#             )
#         ),
#     ),
# ):
#     logger.info("User: {}", email)

#     if not verify_email(email):
#         raise HTTPException(fastapi.status.HTTP_401_UNAUTHORIZED, "Not authenticated")

#     return annotate_doc(doc, "ee")


@app.post(
    f"{URL_PREFIX}/entity_linking",
    response_model=EntityLinkingData,
    tags=["Models"],
    summary="Entity Linking Model",
    description="Use this model to extract entity mentions "
    "linked to UMLS concepts from a given document",
    response_description="Return the list of predicted entity mentions "
    "linked to UMLS concepts",
)
def entity_linking(
    email: str = Query(
        ..., description="Your email address", example="example@domain.com"
    ),
    doc: Doc = Body(
        ...,
        description="The document that needs to be annotated",
        example=asdict(
            Doc(
                "BACKGROUND: Fibroblastic foci are characteristic features in "
                "lung parenchyma of patients with idiopathic pulmonary fibrosis (IPF)."
            )
        ),
    ),
):
    logger.info("User: {}", email)

    if not verify_email(email):
        raise HTTPException(fastapi.status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    return annotate_doc(doc, "el")


# @app.post(
#     f"{URL_PREFIX}/disease_network",
#     response_model=DiseaseNetworkData,
#     tags=["Models"],
#     summary="Disease Network Generation",
#     description="Use this to generate the graph data and visualization "
#     "for the 2D and 3D Disease Networks",
#     response_description="Return the graph data and visualization webpages "
#     "for the 2D and 3D Disease Networks",
# )
# def disease_network(
#     email: str = Query(
#         ..., description="Your email address", example="example@domain.com"
#     ),
#     docs: List[DiseaseNetworkDoc] = Body(
#         ...,
#         description="The list of input data where each element contains "
#         "the list of entities extracted by the entity linking model and "
#         "the list of entities and events extracted by the event extraction "
#         "model from the same document",
#     ),
# ):
#     logger.info("User: {}", email)

#     if not verify_email(email):
#         raise HTTPException(fastapi.status.HTTP_401_UNAUTHORIZED, "Not authenticated")

#     max_args = 0
#     all_events = []

#     for doc_idx, doc in enumerate(docs, start=1):
#         norm_map = {
#             (entity.span.start, entity.span.end): entity
#             for entity in doc.linked_entities
#         }

#         entities = {}

#         for entity in doc.entities:
#             if (entity.span.start, entity.span.end) in norm_map:
#                 entity.concept_id = norm_map[
#                     entity.span.start, entity.span.end
#                 ].concept_id
#                 entity.concept_name = norm_map[
#                     entity.span.start, entity.span.end
#                 ].concept_name

#             entities[entity.id] = entity

#         events = {event.id: event for event in doc.events}

#         for event in events.values():
#             max_args = max(max_args, len(event.args))

#             obj = {
#                 "article_id": doc_idx,
#                 "event_id": event.id,
#                 "event_type": entities[event.trigger_id].type,
#                 "trigger_id": event.trigger_id,
#                 "trigger_str": entities[event.trigger_id].text,
#                 "trigger_canonical_name": entities[event.trigger_id].concept_name,
#                 "trigger_umls_id": entities[event.trigger_id].concept_id,
#             }

#             for arg_index, event_arg in enumerate(event.args, start=1):
#                 if event_arg.arg_id.startswith("E"):
#                     event_arg.arg_id = events[event_arg.arg_id].trigger_id

#                 obj[f"argument_id_{arg_index}"] = event_arg.arg_id
#                 obj[f"argument_type_{arg_index}"] = entities[event_arg.arg_id].type
#                 obj[f"argument_str_{arg_index}"] = entities[event_arg.arg_id].text
#                 obj[f"argument_canonical_name_{arg_index}"] = entities[
#                     event_arg.arg_id
#                 ].concept_name
#                 obj[f"argument_umls_id_{arg_index}"] = entities[
#                     event_arg.arg_id
#                 ].concept_id
#                 obj[f"argument_role_type_{arg_index}"] = event_arg.arg_role

#             all_events.append(obj)

#     logger.info("Max args: {}", max_args)

#     cols = [
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

#     all_events_for_2d = []
#     all_events_for_3d = []

#     for event in all_events:
#         all_events_for_2d.append({col: event.get(col, None) for col in cols})

#         arg_indices = [
#             arg_index
#             for arg_index in range(1, max_args + 1)
#             if f"argument_id_{arg_index}" in event
#         ]

#         if len(arg_indices) > 1:
#             for arg_index_1, arg_index_2 in itertools.combinations(arg_indices, 2):
#                 all_events_for_3d.append(
#                     (
#                         "["
#                         + str(event.get(f"argument_type_{arg_index_1}", None))
#                         + ", "
#                         + str(event.get(f"argument_umls_id_{arg_index_1}", None))
#                         + ", "
#                         + str(event.get(f"argument_canonical_name_{arg_index_1}", None))
#                         + "]: "
#                         + str(event.get(f"argument_str_{arg_index_1}", None)),
#                         str(event.get(f"argument_type_{arg_index_1}", None)),
#                         "["
#                         + str(event.get(f"argument_type_{arg_index_2}", None))
#                         + ", "
#                         + str(event.get(f"argument_umls_id_{arg_index_2}", None))
#                         + ", "
#                         + str(event.get(f"argument_canonical_name_{arg_index_2}", None))
#                         + "]: "
#                         + str(event.get(f"argument_str_{arg_index_2}", None)),
#                         str(event.get(f"argument_type_{arg_index_2}", None)),
#                     )
#                 )

#     data_for_2d_graph = disease_network_generator_for_2d.get_graph_data(
#         all_events_for_2d
#     )

#     df = pd.DataFrame(
#         all_events_for_3d, columns=["SRC_NAME", "SRC_TYPE", "DST_NAME", "DST_TYPE"]
#     )
#     data_for_3d_graph = disease_network_generator_for_3d.get_graph_data(df)

#     visualization_2d = None
#     visualization_3d = None

#     if all_events:
#         visualization_2d = file_utils.read_text("api_2d_graph.html").replace(
#             "{{graph_data}}", json.dumps(data_for_2d_graph)
#         )

#         cache_dir = ".cache/api_for_openplatform/disease_network"

#         file_utils.make_dirs(cache_dir)

#         with tempfile.TemporaryDirectory(dir=cache_dir) as dirname:
#             output_file_for_3d_graph = os.path.join(dirname, "3d_graph.html")

#             disease_network_generator_for_3d.save_graph(
#                 data_for_3d_graph, output_file_for_3d_graph
#             )

#             if os.path.isfile(output_file_for_3d_graph):
#                 visualization_3d = file_utils.read_text(output_file_for_3d_graph)

#     return DiseaseNetworkData(
#         graph_data=all_events,
#         visualization_2d=visualization_2d,
#         visualization_3d=visualization_3d,
#     )


if __name__ == "__main__":
    logger.info("Running in debug mode")

    uvicorn.run(app, host=socket.gethostname(), port=9090)
