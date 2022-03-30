# -*- coding: utf-8 -*-
from loguru import logger

from annotator import SemELAnnotator
from wsgi.config import config


def init_cache():
    el_model = SemELAnnotator(
        config["ner_dir"],
        config["cg_dir"],
        config["cr_dir"],
        config["kbe_dir"],
        config["gss_dir"],
        ".cache",
        True,
    )

    logger.info(el_model("This is for constructing UMLS cache"))


if __name__ == "__main__":
    init_cache()
