# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
from queue import Queue
from tempfile import mkdtemp
from threading import Thread
import os

from disease_network_generator import generate_graph_data, generate_status
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
OUTPUT_FILE_FOR_2D_GRAPH = "2d_graph.json"
OUTPUT_FILE_FOR_3D_GRAPH = "3d_disease_network.html"

MB = 1024 * 1024
MAX_CONTENT_LENGTH = 1024 * MB

queue = Queue()
frontend = Blueprint("Disease Network Visualization", __name__, static_folder="static")


@frontend.route("/")
def index():
    return render_template("index.html", samples=samples, app_name=frontend.name)


@frontend.route("/submit", methods=["POST"])
def submit():
    file_utils.make_dirs(JOB_DIR)

    job_dir = Path(mkdtemp(dir=JOB_DIR))
    job_id = job_dir.name

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
            "graph2DURL": url_for(".view_2d_disease_network", job_id=job_id),
            "graph3DURL": url_for(".view_3d_disease_network", job_id=job_id),
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

    if not output_file_path_for_graph.exists():
        return redirect(url_for(".index"))

    return send_file(output_file_path_for_graph, max_age=-1)


@frontend.route("/graph/<job_id>")
def view_disease_network(job_id):
    job_dir = JOB_DIR / job_id
    output_file_path_for_graph = job_dir / OUTPUT_FILE_FOR_GRAPH

    if not output_file_path_for_graph.exists():
        return redirect(url_for(".index"))

    return render_template(
        "graph.html",
        app_name=frontend.name,
        graph_data=url_for(".fetch_graph_data", job_id=job_id),
    )


@frontend.route("/2d_graph_data/<job_id>")
def fetch_2d_graph_data(job_id):
    job_dir = JOB_DIR / job_id
    output_file_path_for_2d_graph = job_dir / OUTPUT_FILE_FOR_2D_GRAPH

    if not output_file_path_for_2d_graph.exists():
        return redirect(url_for(".index"))

    return send_file(output_file_path_for_2d_graph, max_age=-1)


@frontend.route("/2d_disease_network/<job_id>")
def view_2d_disease_network(job_id):
    job_dir = JOB_DIR / job_id
    output_file_path_for_2d_graph = job_dir / OUTPUT_FILE_FOR_2D_GRAPH

    if not output_file_path_for_2d_graph.exists():
        return redirect(url_for(".index"))

    return render_template(
        "2d_disease_network_index.html",
        app_name=frontend.name,
        graph_data=url_for(".fetch_2d_graph_data", job_id=job_id),
    )


@frontend.route("/3d_disease_network/<job_id>")
def view_3d_disease_network(job_id):
    job_dir = JOB_DIR / job_id
    output_file_path_for_3d_graph = job_dir / OUTPUT_FILE_FOR_3D_GRAPH

    if not output_file_path_for_3d_graph.exists():
        return redirect(url_for(".index"))

    return send_file(output_file_path_for_3d_graph, max_age=-1)


def process_job(job_dir):
    output_file_path_for_graph = job_dir / OUTPUT_FILE_FOR_GRAPH
    output_file_path_for_2d_graph = job_dir / OUTPUT_FILE_FOR_2D_GRAPH
    output_file_path_for_3d_graph = job_dir / OUTPUT_FILE_FOR_3D_GRAPH
    status_file_path = job_dir / STATUS_FILE_NAME

    docs = [(fn.name, file_utils.read_text(fn)) for fn in job_dir.glob("*.txt")]

    generate_graph_data(
        docs,
        str(output_file_path_for_graph),
        str(output_file_path_for_2d_graph),
        str(output_file_path_for_3d_graph),
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

    app.register_blueprint(frontend, url_prefix="/disease_network")

    return app
