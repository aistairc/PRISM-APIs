# PRISM-APIs

[https://github.com/aistairc/PRISM-APIs](https://github.com/aistairc/PRISM-APIs)

This repository contains the source code and data files of the following items:

- Web application for our named entity recognition model. It uses the named entity recognition model from the repository [PRISM-EL](https://github.com/aistairc/PRISM-EL).
- Web application for our bio entity linking model. It uses the entity linking model from the repository [PRISM-EL](https://github.com/aistairc/PRISM-EL).
- Web application for our relation extraction model. It uses the relation extraction model from the repository [PRISM-DeepEM](https://github.com/aistairc/PRISM-DeepEM).
- Web application for our event extraction model. It uses the event extraction model from the repository [PRISM-DeepEM](https://github.com/aistairc/PRISM-DeepEM).
- Web application for our disease network
- API Services

Currently, all the models provided above were trained on our IPF Genes corpus. Please also note that this repository is just for visualizing the output of our NLP models in different ways, so it does not include the source code for training those models from scratch. If you would like to retrain those models on your own data, please check out the corresponding repositories mentioned above.

For the API services, we also have another repository [API Usage Examples](https://github.com/aistairc/kirt-api-docs) containing code examples for our end-users to help interact with our API endpoints properly.

## Requirements

```bash
# On ABCI, please first run the following commands (the version numbers must be the same):
# module load gcc/7.4.0

# Create a virtual environment
conda create -y -n api python=3.8

# Activate the virtual environment
conda activate api

# Install required packages
conda install -y ruby -c conda-forge
conda install -y faiss-cpu==1.7.0 -c conda-forge

pip install torch==1.8.1
pip install overrides==3.1.0
pip install allennlp==0.9.0
pip install loguru==0.6.0
pip install sqlitedict==2.0.0
pip install Bootstrap-Flask==1.5.1
pip install fastapi==0.73.0
pip install "uvicorn[standard]==0.17.1"
pip install pandas==1.2.3
pip install tabulate==0.8.7
pip install pytorch-nlp==0.5.0
pip install python-igraph==0.9.6
pip install plotly==5.1.0

# Compile Geniass model
cd "tools/geniass" && make && cd "../.."
```

Then, please download our trained models using this link [api-data.zip](https://onedrive.live.com/download?cid=8431183F2463E6CB&resid=8431183F2463E6CB%21305&authkey=AN2A1bOjp1Rifjc) and then unpack all of them into the root folder of this repository.

In case you are training models from scratch and also using your own UMLS knowledge base, you should run this command once to create a cache file. Please modify the paths in `config.ini` file and then run:

```bash
python init_cache.py
```

Then you also need to run this command once to normalize your UMLS concept embeddings:

```bash
python normalize_concept_embeddings.py
```

## Deploy web applications and APIs

In order to deploy web applications for our models `named entity recognition, entity linking, relation extraction, and event extraction`, please run this command:

```bash
FLASK_APP=wsgi flask run --host=0.0.0.0 -p 9091
```

The web applications can be accessible at these links:

- http://127.0.0.1:9091/named_entity_recognition/
- http://127.0.0.1:9091/entity_linking/
- http://127.0.0.1:9091/relation_extraction/
- http://127.0.0.1:9091/event_extraction/

In order to deploy web application for our Disease Network, please run this command:

```bash
FLASK_APP=disease-network flask run --host=0.0.0.0 -p 9092
```

Then, you can access the web application using this link:

```bash
http://127.0.0.1:9092/disease_network/
```

For API services, we need to start both two versions for different purposes:

```bash
uvicorn api:app --host 0.0.0.0 --port 9093
uvicorn api_for_openplatform:app --host 0.0.0.0 --port 9094
```

Then, you can access it via the following links:

```bash
http://127.0.0.1:9093/api
http://127.0.0.1:9094/api-for-openplatform
```
