import os
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
import zipfile
import shutil
from werkzeug.utils import safe_join

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

def remove_spaces_from_folders(root_dir):
    for dirpath, dirnames, _ in os.walk(root_dir, topdown=False):
        for dirname in dirnames:
            if ' ' in dirname:
                new_dirname = dirname.replace(' ', '_')
                old_path = os.path.join(dirpath, dirname)
                new_path = os.path.join(dirpath, new_dirname)
                
                # If the target directory exists and is not the same as the current directory, attempt merge or rename
                if os.path.exists(new_path) and old_path != new_path:
                    try:
                        # Attempt to merge contents safely or consider other logic here
                        print(f"Directory already exists: {new_path}. Consider merging or handling differently.")
                    except OSError as e:
                        print(f"Error renaming {old_path} to {new_path}: {e}")
                else:
                    try:
                        os.rename(old_path, new_path)
                    except OSError as e:
                        print(f"Error renaming {old_path} to {new_path}: {e}")

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

# @app.route('/dicom/<path:filename>')
# def serve_dicom_file(filename):
#     return send_from_directory('uploads/extracted/Unnamed_-_0', filename)

@app.route('/dicom/<path:filename>')
def serve_dicom_file(filename):
    # Base directory where DICOM files are stored
    base_dir = os.path.abspath(app.config['EXTRACTED_FOLDER'])
    
    # Create a secure, absolute file path
    file_path = safe_join(base_dir, filename)
    
    if not os.path.exists(file_path):
        return "File not found", 404
    
    # Serve the file from its directory
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))


@app.route('/list-dicom-files')
def list_dicom_files():
    dicom_files = []
    for root, dirs, files in os.walk(app.config['EXTRACTED_FOLDER']):
        for file in files:
            if file.lower().endswith('.dcm'):
                # Generate a relative path to the file from the EXTRACTED_FOLDER
                relative_path = os.path.relpath(os.path.join(root, file), start=app.config['EXTRACTED_FOLDER'])
                dicom_files.append(relative_path)

    # Sort the list of DICOM files alphabetically by their relative paths
    dicom_files.sort()

    return jsonify(dicom_files)

@app.after_request
def after_request(response):
    print("In after_request")
    print(response.headers)
    return response


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')

