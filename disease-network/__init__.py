# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
import shutil
from queue import Queue
from tempfile import mkstemp
from threading import Thread
from multiprocessing import Manager
import os
import json
import uuid
import tarfile

from disease_network_generator import generate_graph_data, generate_status
from disease_network_3d_plot import create_3d_plot_html
from flask import (
    Blueprint,
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask.json import jsonify
from flask_bootstrap import Bootstrap
from utils import file_utils
from werkzeug.utils import secure_filename
from werkzeug.exceptions import NotFound

from .config import samples


VERSION="0.4"


JOB_DIR = Path(os.environ.get('JOB_DIR', './.cache/disease-network')).resolve()

STATUS_FILE_NAME = "status.json"
OUTPUT_FILE_FOR_GRAPH = "graph.json"

MB = 1024 * 1024
MAX_CONTENT_LENGTH = 1024 * MB

queue = Queue()
frontend = Blueprint("Disease Network Constructor", __name__, static_folder="static")


old_job_list = [
    path.name
    for path in sorted(JOB_DIR.glob("*"), key=os.path.getmtime)
    if not (path / OUTPUT_FILE_FOR_GRAPH).is_file()
]

manager = Manager()
job_lock = manager.Lock()
current_job_processed_files = manager.Value('i', 0)
current_job_total_files = manager.Value('i', 0)
jobs = manager.list(old_job_list)
job_files = manager.dict({
    job_id: sum(1 for _ in (JOB_DIR / job_id).glob("*.txt"))
    for job_id in old_job_list
})
for job_id in old_job_list:
    status_file_path = JOB_DIR / job_id / STATUS_FILE_NAME
    if status_file_path.is_file():
        status_file_path.unlink()
    queue.put(job_id)
old_job_list = None



def ensure_uuid(job_id):
    try:
        return str(uuid.UUID(job_id))
    except:
        raise NotFound()


@frontend.route("/")
def index():
    return render_template("index.html",
        samples=samples,
        app_name=frontend.name,
        version=VERSION,
    )


@frontend.route("/submit", methods=["POST"])
def submit():
    job_id = str(uuid.uuid4())
    job_dir = JOB_DIR / job_id
    job_dir.mkdir(exist_ok=True, parents=True)

    num_docs = 0
    if "text" in request.form:
        file = job_dir / "input.txt"
        file.write_text(request.form["text"])
        num_docs = 1
    else:
        for fn in request.files.getlist("file"):
            filename = secure_filename(fn.filename)
            if filename.endswith(".txt"):
                fn.save(job_dir / filename)
                num_docs += 1

    if not num_docs:
        return redirect(url_for(".index"))

    with job_lock:
        jobs.append(job_id)
        job_files[job_id] = num_docs

    queue.put(job_id)

    url = url_for(".view", job_id=job_id)
    return redirect(url)


@frontend.route("/<job_id>")
def view(job_id):
    job_id = ensure_uuid(job_id)
    job_dir = JOB_DIR / job_id
    status_file_path = job_dir / STATUS_FILE_NAME

    if not job_dir.is_dir():
        return abort(404)

    return render_template(
        "view.html",
        page_data={
            "statusURL": url_for(".status", job_id=job_id),
            "graphURL": url_for(".view_disease_network", job_id=job_id),
            "abortURL": url_for(".abort", job_id=job_id),
            "indexURL": url_for(".index"),
        },
        app_name=frontend.name,
        version=VERSION,
    )


@frontend.route("/abort/<job_id>", methods=["POST"])
def abort(job_id):
    job_id = ensure_uuid(job_id)
    job_dir = JOB_DIR / job_id
    if not job_dir.is_dir():
        return abort(404)


    with job_lock:
        if job_id in job_files:
            job_files.pop(job_id)
            jobs.remove(job_id)

    abort_dir = JOB_DIR / (job_id + ".aborted")
    # since rmtree is not atomic, first move atomically out of the way
    job_dir.rename(abort_dir)
    shutil.rmtree(abort_dir)
    return ('', 204)



@frontend.route("/status/<job_id>")
def status(job_id):
    job_id = ensure_uuid(job_id)
    job_dir = JOB_DIR / job_id
    if not job_dir.is_dir():
        return jsonify({ "aborted": True })

    status_file_path = job_dir / STATUS_FILE_NAME
    if not status_file_path.exists():
        with job_lock:
            try:
                job_ix = jobs.index(job_id)
            except KeyError:
                # XXX TODO
                return abort(404)
            remaining_docs = sum(
                [job_files[jobs[ix]] for ix in range(job_ix)],
                current_job_total_files.value - current_job_processed_files.value,
            )
        return jsonify({
            "queue": remaining_docs,
        })

    return send_file(status_file_path, max_age=-1)


@frontend.route("/graph_data/<job_id>")
def fetch_graph_data(job_id):
    job_id = ensure_uuid(job_id)
    job_dir = JOB_DIR / job_id
    output_file_path_for_graph = job_dir / OUTPUT_FILE_FOR_GRAPH

    if not output_file_path_for_graph.is_file():
        return redirect(url_for(".index"))

    return send_file(output_file_path_for_graph, max_age=-1)


@frontend.route("/job_data/<job_id>")
def fetch_job_data(job_id):
    job_id = ensure_uuid(job_id)
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
    job_id = ensure_uuid(job_id)
    job_dir = JOB_DIR / job_id
    output_file_path_for_doc = job_dir / f"{doc_id}.json"

    if not output_file_path_for_doc.exists():
        return redirect(url_for(".index"))

    return send_file(output_file_path_for_doc, max_age=-1)


@frontend.route("/graph/<job_id>")
def view_disease_network(job_id):
    job_id = ensure_uuid(job_id)
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
            job_id = ensure_uuid(names[0])
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
        graph_data=graph_data,
        doc_data_base=doc_data_base,
        job_data=job_data,
        app_name=frontend.name,
        version=VERSION,
    )


def process_job(job_dir):
    output_file_path_for_graph = job_dir / OUTPUT_FILE_FOR_GRAPH
    status_file_path = job_dir / STATUS_FILE_NAME
    job_id = job_dir.name

    if not job_dir.is_dir():
        return

    docs = [(fn.name, file_utils.read_text(fn)) for fn in job_dir.glob("*.txt")]

    with job_lock:
        jobs.remove(job_id)
        current_job_total_files.value = job_files.pop(job_id)
        current_job_processed_files.value = 0

    generate_status(0, len(docs), False, status_file_path)
    generate_graph_data(
        docs,
        str(output_file_path_for_graph),
        status_file_path,
        current_job_processed_files,
        job_lock,
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
