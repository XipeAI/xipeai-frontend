import os
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
import zipfile

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5000"])
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, EXTRACTED_FOLDER)

# Ensure UPLOAD_FOLDER exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Ensure EXTRACTED_FOLDER exists
os.makedirs(app.config['EXTRACTED_FOLDER'], exist_ok=True)

# Define the path to your 'src' directory relative to 'app.py'
src_dir = os.path.abspath('src/')

@app.route('/')
def index():
    # Specify the path and file you want to serve
    return send_from_directory(src_dir, 'index.html')

def remove_spaces_from_folders(start_path):
    for dirpath, dirnames, filenames in os.walk(start_path, topdown=False):
        for dirname in dirnames:
            if ' ' in dirname:
                new_dirname = dirname.replace(' ', '_')
                os.rename(os.path.join(dirpath, dirname), os.path.join(dirpath, new_dirname))

@app.route('/upload', methods=['POST'])
def upload_file():
    if not request.files:
        return 'No file part in the request'
    
    # Get the first uploaded file
    file = next(request.files.values(), None)
    
    if file and file.filename:
        if file.filename.endswith('.zip'):
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(zip_path)
            
            # Extract the ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(app.config['EXTRACTED_FOLDER'])
                
                # Remove spaces from folder names
                remove_spaces_from_folders(app.config['EXTRACTED_FOLDER'])
                
            return redirect(url_for('index'))
        else:
            return 'Invalid file format'
    else:
        return 'No file selected for upload'

@app.route('/dicom/<path:filename>')
def serve_dicom_file(filename):
    return send_from_directory(app.config['EXTRACTED_FOLDER'], filename)

@app.route('/list-dicom-files')
def list_dicom_files():
    dicom_files = []
    for root, dirs, files in os.walk(app.config['EXTRACTED_FOLDER']):
        for file in files:
            if file.lower().endswith('.dcm'):
                # Generate a relative path to the file from the EXTRACTED_FOLDER
                relative_path = os.path.relpath(os.path.join(root, file), start=app.config['EXTRACTED_FOLDER'])
                dicom_files.append(relative_path)
    return jsonify(dicom_files)

@app.after_request
def after_request(response):
    print("In after_request")
    print(response.headers)
    return response


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')

