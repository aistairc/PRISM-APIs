# -*- coding: utf-8 -*-
import re

_SECTION_RE = re.compile(r"\[(.*?)\]")

DEFAULT_KINDS = [
    "SPAN_DEFAULT",
    "ARC_DEFAULT",
    "ATTRIBUTE_DEFAULT",
]


def _parse_attrs(attribute_text, labels):
    attributes = dict(item.strip().split(":") for item in attribute_text.split(","))
    attributes["labels"] = labels
    return attributes


def parse_visual_conf(filename):
    """
    Reads simple brat visual configuration files.
    Just simple ones. No macros, defaults...
    """

    with open(filename, "rt") as r:
        text = r.read()

    # section_texts = _SECTION_RE.split(text)
    it = iter(_SECTION_RE.split(text))
    next(it)
    sections = dict(
        (
            key,
            [
                line
                for line in text.strip().split("\n")
                if line.strip() and not line.startswith("#")
            ],
        )
        for key, text in zip(it, it)
    )
    labels = {
        name.strip(): [label.strip() for label in labels]
        for name, *labels in (line.split("|") for line in sections.get("labels", []))
    }
    conf = {
        name: _parse_attrs(attributes, labels.get(name, []))
        for name, attributes in (
            parts
            for parts in (line.split("\t", 2) for line in sections.get("drawing", []))
            if len(parts) == 2
        )
    }

    defaults = {k: conf.pop(k, {}) for k in DEFAULT_KINDS}

    return (conf, defaults)
