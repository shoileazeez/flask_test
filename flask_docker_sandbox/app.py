import os
import zipfile
import uuid
import subprocess
from flask import Flask, request, jsonify, render_template

UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_zip():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save ZIP file with unique name
    file_id = str(uuid.uuid4())
    filename = f"{file_id}.zip"
    zip_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(zip_path)

    # Extract to a unique folder
    extract_path = os.path.join(UPLOAD_FOLDER, file_id)
    os.makedirs(extract_path, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    # Docker build & run
    image_name = f"sandbox_{file_id}"
    container_name = f"container_{file_id}"

    build_cmd = ["docker", "build", "-t", image_name, extract_path]
    run_cmd = ["docker", "run", "-d", "--rm", "--name", container_name, image_name]

    build_result = subprocess.run(build_cmd, capture_output=True, text=True)
    if build_result.returncode != 0:
        return jsonify({"error": "Docker build failed", "details": build_result.stderr}), 500

    run_result = subprocess.run(run_cmd, capture_output=True, text=True)
    if run_result.returncode != 0:
        return jsonify({"error": "Docker run failed", "details": run_result.stderr}), 500

    return jsonify({"status": "success", "container": container_name})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)