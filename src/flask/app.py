import os
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session
from flask_cors import CORS
import zipfile
import shutil
from werkzeug.utils import safe_join
import pydicom
from pydicom.data import get_testdata_files
import secrets
from urllib.parse import unquote


app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5000"])
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, EXTRACTED_FOLDER)
secret_key = secrets.token_urlsafe(24)
app.secret_key = secret_key  


@app.route('/dicom-metadata/dummy')
def dicom_metadata_dummy():
    dummy_data = [
        {"Field": "Name", "Value": "Sagway"},
        {"Field": "First Name", "Value": "Donald"},
        {"Field": "Patient ID", "Value": "6594589"},
        {"Field": "Acquisition Date", "Value": "05.02.2026"},
        {"Field": "Acquisition Time", "Value": "05:20:11"},
        {"Field": "Result", "Value": "Critical(1)"},
        {"Field": "Area (1)", "Value": "25mm²"},
        {"Field": "Position (1)", "Value": "x25 y37"},
        {"Field": "Area (2)", "Value": "NA"},  # Assuming NA means data not available
        {"Field": "Position (2)", "Value": "NA"},  # Assuming NA means data not available
        # ... add more fields as needed
    ]
    return jsonify(dummy_data)
 
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
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # Rename files with spaces
        for filename in filenames:
            if ' ' in filename:
                new_filename = filename.replace(' ', '_')
                old_file_path = os.path.join(dirpath, filename)
                new_file_path = os.path.join(dirpath, new_filename)
                os.rename(old_file_path, new_file_path)

        # Rename directories with spaces
        for dirname in dirnames:
            if ' ' in dirname:
                new_dirname = dirname.replace(' ', '_')
                old_dir_path = os.path.join(dirpath, dirname)
                new_dir_path = os.path.join(dirpath, new_dirname)
                
                # Rename the directory
                if not os.path.exists(new_dir_path):
                    os.rename(old_dir_path, new_dir_path)
                else:
                    print(f"Directory cannot be renamed because {new_dir_path} already exists")


@app.route('/upload', methods=['POST'])
def upload_file():
    if not request.files:
        return 'No file part in the request'

    file = next(request.files.values(), None)

    if file and file.filename and file.filename.endswith('.zip'):
        # Clear existing content in the EXTRACTED_FOLDER
        for root, dirs, files in os.walk(app.config['EXTRACTED_FOLDER'], topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

        # Save and extract the ZIP file to the EXTRACTED_FOLDER
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(app.config['EXTRACTED_FOLDER'])

        # After extracting files:
        remove_spaces_from_folders(app.config['EXTRACTED_FOLDER'])

        # Get the list of subfolders
        subfolders = get_subfolders(app.config['EXTRACTED_FOLDER'])
        session['subfolders'] = subfolders

        # ... (the rest of the code in the upload endpoint if there is more)

        return redirect(url_for('index'))
    else:
        return 'Invalid file format or no file selected'

def get_subfolders(directory, parent_folder=""):
    subfolders_list = []
    # Iterate over all the items in directory
    for item in os.scandir(directory):
        if item.is_dir():  # Check if it is a directory
            full_path = os.path.join(parent_folder, item.name)
            subfolders_list.append(full_path)  # Add the subfolder to the list
            # Recursively check for further subfolders
            subfolders_list.extend(get_subfolders(item.path, full_path))
    return subfolders_list

@app.route('/subfolders', methods=['GET'])
def get_subfolders_route():
    # Return the list of subfolders stored in the session
    return jsonify(session.get('subfolders', []))
 
@app.route('/dicom/<path:filename>')
def serve_dicom_file(filename):
    # Log the received filename for debugging
    print(f"Requested file: {filename}")

    base_dir = os.path.abspath(app.config['EXTRACTED_FOLDER'])
    file_path = safe_join(base_dir, filename)

    # Log the absolute file path for debugging
    print(f"Full file path: {file_path}")

    if not os.path.exists(file_path):
        return "File not found", 404
    
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))




@app.route('/list-dicom-files')
def list_dicom_files():
    selected_subfolder = request.args.get('subfolder')
    print(f"Requested subfolder: {selected_subfolder}")  # For debugging

    if selected_subfolder is None:
        return jsonify({"error": "No subfolder provided"}), 400
    
    # Ensure the subfolder exists
    subfolder_path = os.path.join(app.config['EXTRACTED_FOLDER'], selected_subfolder)
    if not os.path.exists(subfolder_path):
        return jsonify({"error": "Subfolder not found"}), 404

    # List DICOM files
    dicom_files = []
    for root, dirs, files in os.walk(subfolder_path):
        for file in files:
            if file.lower().endswith('.dcm'):
                # Generate a relative path to the file from the EXTRACTED_FOLDER
                relative_path = os.path.relpath(os.path.join(root, file), start=root)
                dicom_files.append(relative_path)

    # Sort the list of DICOM files alphabetically by their relative paths
    dicom_files.sort()
    return jsonify(dicom_files)

 
@app.after_request
def after_request(response):
    print("In after_request")
    print(response.headers)
    return response
 
@app.route('/dicom-metadata/<path:filename>')
def dicom_metadata(filename):
    # Base directory where DICOM files are stored
    base_dir = os.path.abspath(app.config['EXTRACTED_FOLDER'])
    # Create a secure, absolute file path
    dicom_file_path = safe_join(base_dir, filename)

    # Ensure the file exists
    if not os.path.exists(dicom_file_path):
        return jsonify({'error': 'File not found'}), 404

    # Extract the metadata from the DICOM file
    ds = pydicom.dcmread(dicom_file_path)
    print(ds)

    # Define which metadata fields you want to extract
    metadata_fields = [
        ('PatientName', 'PatientID'), 
        ('PatientBirthDate', 'Patient Birth Date'), 
        ('BodyPartExamined', 'Body Part Examined'), 
        ('StudyTime', 'Study Time'),
        ('Result', 'Result'),
        ('AccessionNumber', 'Accession Number'), 
        ('Modality', 'Modality'), 
        ('StudyDescription', 'Study Description')
        
    ]

    # Extract the required metadata fields and preserve order in a list
    ordered_metadata = [
        {"Field": display, "Value": str(getattr(ds, tag, 'NA'))}
        for tag, display in metadata_fields
    ]

    return jsonify(ordered_metadata)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')