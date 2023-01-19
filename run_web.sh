#!/bin/bash

# http://127.0.0.1:5002/named_entity_recognition/
# http://127.0.0.1:5002/entity_linking/
# http://127.0.0.1:5002/relation_extraction/
# http://127.0.0.1:5002/event_extraction/
FLASK_APP=wsgi flask run --host=0.0.0.0 -p 5002 &

# http://127.0.0.1:5003/disease_network/
# FLASK_APP=disease-network flask run --host=0.0.0.0 -p 5003 &

# http://127.0.0.1:5004/api
uvicorn api:app --host 0.0.0.0 --port 5004 &

# http://127.0.0.1:5005/api-for-openplatform
uvicorn api_for_openplatform:app --host 0.0.0.0 --port 5005 &

echo 'alias q="FLASK_APP=disease-network flask run --host=0.0.0.0 -p 5003"'

wait

