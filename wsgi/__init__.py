# -*- coding: utf-8 -*-
from annotator import DeepEMAnnotator, SemELAnnotator
from flask import Flask
from flask_bootstrap import Bootstrap

from .config import config
from .frontend import make_frontend

# thanks to https://github.com/mbr/flask-bootstrap


def create_app(configfile=None):
    # TODO config

    app = Flask(__name__)
    Bootstrap(app)

    ner_model = SemELAnnotator(
        config["ner_dir"],
        config["cg_dir"],
        config["cr_dir"],
        config["kbe_dir"],
        config["gss_dir"],
        ".cache",
        False,
    )
    ner_frontend = make_frontend("Named Entity Recognition", ner_model)
    app.register_blueprint(ner_frontend, url_prefix="/named_entity_recognition")

    el_model = SemELAnnotator(
        config["ner_dir"],
        config["cg_dir"],
        config["cr_dir"],
        config["kbe_dir"],
        config["gss_dir"],
        ".cache",
        True,
    )
    el_frontend = make_frontend("Entity Linking", el_model)
    app.register_blueprint(el_frontend, url_prefix="/entity_linking")

    re_model = DeepEMAnnotator(config["re_cfg"], config["gss_dir"], ".cache")
    re_frontend = make_frontend("DeepEventMine: Relation Extraction", re_model)
    app.register_blueprint(re_frontend, url_prefix="/relation_extraction")

    ev_model = DeepEMAnnotator(config["ev_cfg"], config["gss_dir"], ".cache")
    ev_frontend = make_frontend("DeepEventMine: Event Extraction", ev_model)
    app.register_blueprint(ev_frontend, url_prefix="/event_extraction")

    print("Ready")
    return app
