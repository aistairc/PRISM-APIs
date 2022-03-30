# -*- coding: utf-8 -*-
import os
import pickle
import random

import numpy as np
import torch
from torch.utils.data import DataLoader, SequentialSampler, TensorDataset

from eval.evaluation import eval
from loader.prepData import prepdata
from loader.prepNN import prep4nn
from model import deepEM
from utils import utils


def main():
    inp_args = utils._parsing()
    config_path = getattr(inp_args, "yaml")

    parameters = load_parameters(config_path)
    model = load_model(parameters)
    process_dir(model, parameters)


def load_parameters(config_path):
    with open(config_path, "r") as stream:
        pred_params = utils._ordered_load(stream)

    # Fix seed for reproducibility
    os.environ["PYTHONHASHSEED"] = str(pred_params["seed"])
    random.seed(pred_params["seed"])
    np.random.seed(pred_params["seed"])
    torch.manual_seed(pred_params["seed"])

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    with open(pred_params["params"], "rb") as f:
        parameters = pickle.load(f)
        parameters.update(pred_params)

    if parameters["gpu"] >= 0:
        device = torch.device(
            "cuda:" + str(parameters["gpu"]) if torch.cuda.is_available() else "cpu"
        )

        torch.cuda.set_device(parameters["gpu"])
    else:
        device = torch.device("cpu")

    parameters["device"] = device

    return parameters


def load_model(parameters):
    deepee_model = deepEM.DeepEM(parameters)

    model_path = parameters["joint_model_dir"]
    device = parameters["device"]

    utils.handle_checkpoints(
        model=deepee_model,
        checkpoint_dir=model_path,
        params={"device": device},
        resume=True,
    )

    deepee_model.to(device)

    return deepee_model


def process_dir(deepee_model, parameters, test_data=None, result_dir=None):
    # Avoid data from being overwritten in multithreading (no need to use deep copy)
    parameters = parameters.copy()

    if test_data:
        parameters["test_data"] = test_data
    else:
        test_data = parameters["test_data"]

    if result_dir:
        parameters["result_dir"] = result_dir
    else:
        result_dir = parameters["result_dir"]

    test_data = prepdata.prep_input_data(test_data, parameters)
    nntest_data, test_dataloader = read_test_data(test_data, parameters)

    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    eval(
        model=deepee_model,
        eval_dir=test_data,
        result_dir=result_dir,
        eval_dataloader=test_dataloader,
        eval_data=nntest_data,
        params=parameters,
    )


def read_test_data(test_data, params):
    test, test_events_map = prep4nn.data2network(test_data, "predict", params)

    if len(test) == 0:
        raise ValueError("Test set empty.")

    test_data = prep4nn.torch_data_2_network(
        cdata2network=test,
        events_map=test_events_map,
        params=params,
        do_get_nn_data=True,
    )
    te_data_size = len(test_data["nn_data"]["ids"])

    test_data_ids = TensorDataset(torch.arange(te_data_size))
    test_sampler = SequentialSampler(test_data_ids)
    test_dataloader = DataLoader(
        test_data_ids, sampler=test_sampler, batch_size=params["batchsize"]
    )
    return test_data, test_dataloader


if __name__ == "__main__":
    main()
