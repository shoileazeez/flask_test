import os
import uuid
import zipfile
import shutil
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

running_processes = {}  # To track running apps by UID


@app.route('/')
def index():
    return "Upload endpoint: POST /upload"


@app.route('/upload', methods=['POST'])
def upload_and_run():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    uid = str(uuid.uuid4())
    zip_path = os.path.join(UPLOAD_FOLDER, f"{uid}.zip")
    extract_path = os.path.join(UPLOAD_FOLDER, uid)
    file.save(zip_path)

    # Clean extract directory
    if os.path.exists(extract_path):
        shutil.rmtree(extract_path)
    os.makedirs(extract_path, exist_ok=True)

    # Extract ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    # Find manage.py or package.json recursively
    manage_path = find_file(extract_path, "manage.py")
    package_path = find_file(extract_path, "package.json")

    if manage_path:
        return run_django_project(os.path.dirname(manage_path), uid)
    elif package_path:
        return run_node_project(os.path.dirname(package_path), uid)
    else:
        return jsonify({"error": "Unknown project type"}), 400


def find_file(base_path, filename):
    for root, dirs, files in os.walk(base_path):
        if filename in files:
            return os.path.join(root, filename)
    return None


def get_base_url(port):
    host = request.host.split(':')[0]
    return f"http://{host}:{port}"


def run_django_project(path, uid):
    port = str(8000 + len(running_processes))
    script = f"""
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt || echo 'Skipping requirements'
    python manage.py migrate || echo 'Skipping migrate'
    python manage.py runserver 0.0.0.0:{port}
    """

    log_file = open(os.path.join(path, "log.txt"), "w")
    process = subprocess.Popen(["bash", "-c", script], cwd=path, stdout=log_file, stderr=log_file)
    running_processes[uid] = process

    url = get_base_url(port)
    return jsonify({"status": "Django app running", "url": url, "pid": process.pid})


def run_node_project(path, uid):
    port = str(9000 + len(running_processes))
    script = f"""
    npm install
    PORT={port} node index.js || node app.js
    """

    log_file = open(os.path.join(path, "log.txt"), "w")
    process = subprocess.Popen(["bash", "-c", script], cwd=path, stdout=log_file, stderr=log_file)
    running_processes[uid] = process

    url = get_base_url(port)
    return jsonify({"status": "Node.js app running", "url": url, "pid": process.pid})


@app.route('/stop/<uid>', methods=['POST'])
def stop_process(uid):
    proc = running_processes.get(uid)
    if proc:
        proc.terminate()
        running_processes.pop(uid)
        return jsonify({"status": "Process terminated"})
    return jsonify({"error": "Invalid UID or process not running"}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
