# -*- coding: utf-8 -*-
import json
import os
from collections import OrderedDict
from configparser import ConfigParser, ExtendedInterpolation

config_path = os.environ.get("CONFIG_FILE", "config.ini")
config = ConfigParser(interpolation=ExtendedInterpolation())
config.read(config_path)
config = config["Web"]

with open(config["samples_path"], "rt") as r:
    samples = OrderedDict((item.pop("id"), item) for item in json.load(r))
