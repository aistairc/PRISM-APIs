# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
from queue import Queue
from tempfile import mkstemp
from threading import Thread
import os
import json
import uuid
import tarfile

from disease_network_generator import generate_graph_data, generate_status
from disease_network_3d_plot import create_3d_plot_html
from flask import (
    Blueprint,
    Flask,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_bootstrap import Bootstrap
from utils import file_utils
from werkzeug.utils import secure_filename

from .config import samples

JOB_DIR = Path(os.environ.get('JOB_DIR', './.cache/disease-network')).resolve()

STATUS_FILE_NAME = "status.json"
OUTPUT_FILE_FOR_GRAPH = "graph.json"

MB = 1024 * 1024
MAX_CONTENT_LENGTH = 1024 * MB

queue = Queue()
frontend = Blueprint("Disease Network Visualization", __name__, static_folder="static")


@frontend.route("/")
def index():
    return render_template("index.html", samples=samples, app_name=frontend.name)


@frontend.route("/submit", methods=["POST"])
def submit():
    job_id = str(uuid.uuid4())
    job_dir = JOB_DIR / job_id
    job_dir.mkdir(exist_ok=True, parents=True)

    num_files = 0

    if "text" in request.form:
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w+", encoding="UTF-8", dir=job_dir, delete=False
        ) as temp_file:
            temp_file.write(request.form["text"])
            temp_file.flush()

        num_files += 1
    else:
        for fn in request.files.getlist("file"):
            filename = secure_filename(fn.filename)

            fn.save(job_dir / filename)

            num_files += 1

    queue.put(job_id)

    # Hack
    status_file_path = job_dir / STATUS_FILE_NAME

    generate_status(0, num_files, False, status_file_path)

    url = url_for(".view", job_id=job_id)

    return redirect(url)


@frontend.route("/<job_id>")
def view(job_id):
    job_dir = JOB_DIR / job_id
    status_file_path = job_dir / STATUS_FILE_NAME

    if not status_file_path.exists():
        return redirect(url_for(".index"))

    return render_template(
        "view.html",
        page_data={
            "statusURL": url_for(".status", job_id=job_id),
            "graphURL": url_for(".view_disease_network", job_id=job_id),
        },
        app_name=frontend.name,
    )


@frontend.route("/status/<job_id>")
def status(job_id):
    job_dir = JOB_DIR / job_id
    status_file_path = job_dir / STATUS_FILE_NAME

    if not status_file_path.exists():
        return redirect(url_for(".index"))

    return send_file(status_file_path, max_age=-1)


@frontend.route("/graph_data/<job_id>")
def fetch_graph_data(job_id):
    job_dir = JOB_DIR / job_id
    output_file_path_for_graph = job_dir / OUTPUT_FILE_FOR_GRAPH

    if not output_file_path_for_graph.is_file():
        return redirect(url_for(".index"))

    return send_file(output_file_path_for_graph, max_age=-1)


@frontend.route("/job_data/<job_id>")
def fetch_job_data(job_id):
    job_dir = JOB_DIR / job_id

    if not job_dir.is_dir():
        return redirect(url_for(".index"))

    tgz_file = job_dir / "disease-graph-full.tgz"
    if not tgz_file.is_file():
        with tarfile.open(tgz_file, mode="w:gz") as tgz:
            tgz.add(job_dir, arcname=os.path.basename(job_dir))
    return send_file(tgz_file, max_age=-1)


@frontend.route("/graph/3d", methods=["POST"])
def show_3d_graph():
    data = json.loads(request.form["data"])
    return create_3d_plot_html(data)


@frontend.route("/doc_data/<job_id>/<doc_id>")
def fetch_doc_data(job_id, doc_id):
    job_dir = JOB_DIR / job_id
    output_file_path_for_doc = job_dir / f"{doc_id}.json"

    if not output_file_path_for_doc.exists():
        return redirect(url_for(".index"))

    return send_file(output_file_path_for_doc, max_age=-1)


@frontend.route("/graph/<job_id>")
def view_disease_network(job_id):
    job_dir = JOB_DIR / job_id
    output_file_path_for_graph = job_dir / OUTPUT_FILE_FOR_GRAPH

    if not output_file_path_for_graph.exists():
        return redirect(url_for(".index"))

    graph_data = json.loads(output_file_path_for_graph.read_text())
    doc_data_base = url_for(".fetch_doc_data", job_id=job_id, doc_id='')
    job_data = url_for(".fetch_job_data", job_id=job_id)
    return show_graph(graph_data, doc_data_base, job_data)


@frontend.route("/graph/show_json", methods=["POST"])
def show_json():
    fn = request.files.get("json")
    if not (fn and fn.filename):
        return redirect(url_for(".index"))
    if fn.filename.endswith('.json'):
        graph_data = json.load(fn)
        graph_data = graph_data["elements"]
        return show_graph(graph_data)
    elif fn.filename.endswith('.tgz'):
        tfh, tfn = mkstemp(dir=JOB_DIR)
        tmp_tgz_file = Path(tfn)
        fn.save(tmp_tgz_file)
        with tarfile.open(tmp_tgz_file) as tgz:
            names = tgz.getnames()
            try:
                job_id = str(uuid.UUID(names[0]))
            except:
                return redirect(url_for(".index"))
            prefix = job_id + "/"
            job_dir = JOB_DIR / job_id
            if not job_dir.is_dir():
                if not all(name == job_id or name.startswith(prefix) for name in names):
                    return redirect(url_for(".index"))
                tgz.extractall(JOB_DIR)
                tmp_tgz_file.rename(job_dir / "disease-graph-full.tgz")
            return redirect(url_for(".view_disease_network", job_id=job_id))


def show_graph(graph_data, doc_data_base=None, job_data=None):
    return render_template(
        "graph.html",
        app_name=frontend.name,
        graph_data=graph_data,
        doc_data_base=doc_data_base,
        job_data=job_data,
    )


def process_job(job_dir):
    output_file_path_for_graph = job_dir / OUTPUT_FILE_FOR_GRAPH
    status_file_path = job_dir / STATUS_FILE_NAME

    docs = [(fn.name, file_utils.read_text(fn)) for fn in job_dir.glob("*.txt")]

    generate_graph_data(
        docs,
        str(output_file_path_for_graph),
        status_file_path,
    )


def worker():
    from traceback import print_exc
    while True:
        try:
            job_id = queue.get()

            job_dir = JOB_DIR / job_id

            process_job(job_dir)
        except Exception as x:
            print_exc(x)


def create_app():
    Thread(target=worker).start()

    app = Flask(__name__)

    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    Bootstrap(app)

    url_prefix = os.environ.get('DISEASE_NETWORK_URL_PREFIX', '/disease_network')
    app.register_blueprint(frontend, url_prefix=url_prefix)

    return app
