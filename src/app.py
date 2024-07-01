import os
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template
from flask_cors import CORS
import zipfile
import shutil
from werkzeug.utils import safe_join
import pydicom
from pydicom.data import get_testdata_files
from pydicom.dataset import Dataset, FileDataset
from datetime import datetime
import secrets
from urllib.parse import unquote
import dicom2nifti


app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5000"])
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted'
SEGMENTED_FOLDER = 'segmented'
NIFTI_FOLDER = 'nifti_extracted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, EXTRACTED_FOLDER)
app.config['SEGMENTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, SEGMENTED_FOLDER)
app.config['NIFTI_FOLDER'] = os.path.join(UPLOAD_FOLDER, NIFTI_FOLDER)
secret_key = secrets.token_urlsafe(24)
app.secret_key = secret_key  

def create_dicom_report(output_path, patient_info, tumor_info):
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.generate_uid()
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    file_meta.ImplementationClassUID = pydicom.uid.generate_uid()

    ds = FileDataset(output_path, {}, file_meta=file_meta, preamble=b"\0" * 128)

    ds.PatientName = patient_info['name']
    ds.PatientID = patient_info['id']
    ds.PatientBirthDate = patient_info['birth_date']
    ds.StudyDate = datetime.now().strftime('%Y%m%d')
    ds.StudyTime = datetime.now().strftime('%H%M%S')
    ds.Modality = 'OT'
    ds.StudyDescription = 'Tumor Analysis Report'

    ds.add_new(0x0008103E, 'LO', 'Tumor Information')

    for idx, tumor in enumerate(tumor_info, start=1):
        tumor_str = f"Tumor {idx}: Width={tumor['width']:.2f}mm, Height={tumor['height']:.2f}mm, Depth={tumor['depth']:.2f}mm, Volume={tumor['volume']:.2f}mm³, Density={tumor['density']:.2f}"
        ds.add_new(0x00200010 + idx, 'LO', tumor_str)
        print(f"Added tumor info to DICOM: {tumor_str}")

    ds.save_as(output_path)
    print(f"Report saved as {output_path}")


def extract_patient_and_tumor_info(dicom_files):
    patient_info = {}
    tumor_info = []

    for dicom_file in dicom_files:
        ds = pydicom.dcmread(dicom_file)
        print(f"Reading DICOM file: {dicom_file}")
        print(ds)  # Log the entire DICOM dataset for debugging

        if not patient_info:
            patient_info = {
                'name': str(ds.PatientName) if 'PatientName' in ds else '',
                'id': str(ds.PatientID) if 'PatientID' in ds else '',
                'birth_date': str(ds.PatientBirthDate) if 'PatientBirthDate' in ds else ''
            }
            print(f"Extracted patient info: {patient_info}")

        # Example logic to extract tumor information
        if hasattr(ds, 'SequenceOfUltrasoundRegions'):  # Example tag, replace with actual
            print(f"Found SequenceOfUltrasoundRegions in {dicom_file}")
            for seq in ds.SequenceOfUltrasoundRegions:
                tumor = {
                    'width': float(seq.RegionLocationMaxX1) if 'RegionLocationMaxX1' in seq else 0.0,
                    'height': float(seq.RegionLocationMaxY1) if 'RegionLocationMaxY1' in seq else 0.0,
                    'depth': 5.0,  # Assuming fixed depth, replace with actual if available
                    'volume': float(seq.RegionLocationMaxX1) * float(seq.RegionLocationMaxY1) * 5.0 if 'RegionLocationMaxX1' in seq and 'RegionLocationMaxY1' in seq else 0.0,  # Example calculation
                    'density': float(seq.RegionSpatialFormat) if 'RegionSpatialFormat' in seq else 0.0  # Example tag, replace with actual
                }
                print(f"Extracted tumor info: {tumor}")
                tumor_info.append(tumor)
        else:
            print(f"No SequenceOfUltrasoundRegions found in {dicom_file}")
    
    return patient_info, tumor_info


@app.route('/create-report', methods=['POST'])
def create_report():
    dicom_files = []
    for root, dirs, files in os.walk(app.config['EXTRACTED_FOLDER']):
        for file in files:
            if file.endswith('.dcm'):
                dicom_files.append(os.path.join(root, file))

    if not dicom_files:
        return jsonify({"error": "No DICOM files found"}), 400
    
    try:
        patient_info, tumor_info = extract_patient_and_tumor_info(dicom_files)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tumor_report.dcm')
        
        create_dicom_report(output_path, patient_info, tumor_info)
        return jsonify({"message": "Report created successfully", "report_path": output_path})
    except Exception as e:
        print(f"Error creating report: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/view-report')
def view_report():
    report_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tumor_report.dcm')
    return send_from_directory(os.path.dirname(report_path), os.path.basename(report_path))


@app.route('/dicom-metadata-report')
def dicom_metadata_report():
    report_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tumor_report.dcm')
    ds = pydicom.dcmread(report_path)

    metadata = {
        "Patient Name": str(ds.PatientName) if 'PatientName' in ds else '',
        "Patient ID": str(ds.PatientID) if 'PatientID' in ds else '',
        "Patient Birth Date": str(ds.PatientBirthDate) if 'PatientBirthDate' in ds else '',
        "Study Date": str(ds.StudyDate) if 'StudyDate' in ds else '',
        "Study Time": str(ds.StudyTime) if 'StudyTime' in ds else '',
        "Modality": str(ds.Modality) if 'Modality' in ds else '',
        "Study Description": str(ds.StudyDescription) if 'StudyDescription' in ds else '',
        "Tumor Information": []
    }

    # Extract tumor information
    for elem in ds:
        if elem.tag.group == 0x0020 and elem.tag.element >= 0x0010:
            print(f"Processing element: {elem}")
            tumor_info = elem.value.split(',')
            tumor_data = {}
            for info in tumor_info:
                if '=' in info:
                    key, value = info.split('=')
                    tumor_data[key.strip()] = value.strip()
            metadata["Tumor Information"].append(tumor_data)
            print(f"Extracted tumor data from report: {tumor_data}")

    print(metadata)  # Log the metadata
    return jsonify(metadata)


@app.route('/report-page')
def report_page():
    return render_template('report.html')

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
# Ensure SEGMENTED_FOLDER exists
os.makedirs(app.config['SEGMENTED_FOLDER'], exist_ok=True)
 
# Define the path to your 'src' directory relative to 'app.py'
src_dir = os.path.abspath('src/')
 
@app.route('/')
def index():
    # Specify the path and file you want to serve
    return render_template('index.html')

def create_dicom_report(output_path, patient_info, tumor_info):
    # Create a new DICOM file
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.generate_uid()
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    file_meta.ImplementationClassUID = pydicom.uid.generate_uid()
    
    ds = FileDataset(output_path, {}, file_meta=file_meta, preamble=b"\0" * 128)
    
    # Add patient information
    ds.PatientName = patient_info['name']
    ds.PatientID = patient_info['id']
    ds.PatientBirthDate = patient_info['birth_date']
    ds.StudyDate = datetime.now().strftime('%Y%m%d')
    ds.StudyTime = datetime.now().strftime('%H%M%S')
    ds.Modality = 'OT'  # Other
    ds.StudyDescription = 'Tumor Analysis Report'
    
    # Add custom tumor information
    ds.add_new(0x0008103E, 'LO', 'Tumor Information')
    
    for idx, tumor in enumerate(tumor_info, start=1):
        ds.add_new(0x00200010 + idx, 'LO', f"Tumor {idx}: Volume={tumor['volume']:.2f}mm³, Density={tumor['density']:.2f}")
    
    # Save the DICOM file
    ds.save_as(output_path)
    print(f"Report saved as {output_path}")
 
def remove_spaces_from_folders(root_dir, file_id):
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
                new_dirname = file_id[-8:-4]
                old_dir_path = os.path.join(dirpath, dirname)
                new_dir_path = os.path.join(dirpath, new_dirname)
                
                # Rename the directory
                if not os.path.exists(new_dir_path):
                    os.rename(old_dir_path, new_dir_path)
                else:
                    print(f"Directory cannot be renamed because {new_dir_path} already exists")


def clear_directory(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

def process_dicom_series(extracted_folder, nifti_output_folder, file_id):
    for root, dirs, files in os.walk(extracted_folder):
        if files:  # If there are files in the directory, assume it's a DICOM series
            subfolder_name = os.path.basename(root)
            subfolder_name = os.path.join(file_id[-8:-4], subfolder_name)
            nifti_subfolder_path = os.path.join(nifti_output_folder, subfolder_name)
            os.makedirs(nifti_subfolder_path, exist_ok=True)  # Ensure subfolder exists
            
            try:
                dicom2nifti.convert_directory(root, nifti_subfolder_path)
                print(f"Converted DICOM series in {root} to NIfTI in {nifti_subfolder_path}")
            except Exception as e:
                print(f"Error converting DICOM series in {root}: {e}")
                # Optionally, use `flash(f"Error converting DICOM series in {root}: {e}")` to send feedback to the template


        
@app.route('/upload', methods=['POST'])
def upload_file():
    if not request.files:
        return 'No file part in the request'

    file = next(request.files.values(), None)

    if file and file.filename and file.filename.endswith('.zip'):
        # Your existing code for clearing the EXTRACTED_FOLDER goes here
        clear_directory(app.config['EXTRACTED_FOLDER'])
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Extract all files, skipping __MACOSX and any other undesired files/folders
            for member in zip_ref.infolist():
                if '__MACOSX' not in member.filename:
                    # Ensure target directory exists (handles nested directories)
                    target_path = os.path.join(app.config['EXTRACTED_FOLDER'], member.filename)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    if not os.path.isdir(target_path):  # Avoid trying to extract directories directly
                        zip_ref.extract(member, app.config['EXTRACTED_FOLDER'])

        remove_spaces_from_folders(app.config['EXTRACTED_FOLDER'], file.filename)

        # Get the list of subfolders
        dicom_subfolders = get_subfolders(app.config['EXTRACTED_FOLDER'])
        session['dicom_subfolders'] = dicom_subfolders  # Only update the DICOM subfolders

        # After successfully extracting the files:
        try:
            process_dicom_series(app.config['EXTRACTED_FOLDER'], app.config['NIFTI_FOLDER'], file.filename)
        except Exception as e:
            return str(e), 500


        return redirect(url_for('index'))
    else:
        return 'Invalid file format or no file selected'
    
@app.route('/uploadsegmented', methods=['POST'])
def upload_segmentation_file():
    if not request.files:
        return 'No file part in the request'

    file = next(request.files.values(), None)

    if file and file.filename and file.filename.endswith('.zip'):
        # Clear existing content in the EXTRACTED_FOLDER
        for root, dirs, files in os.walk(app.config['SEGMENTED_FOLDER'], topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        clear_directory(app.config['SEGMENTED_FOLDER'])
        # Save the ZIP file
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(zip_path)

        # Extract the ZIP file while skipping the __MACOSX directory
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(app.config['SEGMENTED_FOLDER'])

        # After extracting files:
        remove_spaces_from_folders(app.config['SEGMENTED_FOLDER'], file.filename)

        # Get the list of subfolders
        segmentation_subfolders = get_subfolders(app.config['SEGMENTED_FOLDER'])
        session['segmentation_subfolders'] = segmentation_subfolders  # Only update the segmentation subfolders

        return redirect(url_for('index'))
    else:
        return 'Invalid file format or no file selected'

 

def get_subfolders(directory, root_dir=None):
    if root_dir is None:
        root_dir = directory

    subfolders_list = []
    for item in os.scandir(directory):
        if item.is_dir():
            # Recursive call to get subfolders of subfolders
            subfolder_paths = get_subfolders(item.path, root_dir)
            # Only add subdirectories that are not the root directory
            if item.path != root_dir:
                subfolders_list.append(os.path.relpath(item.path, root_dir))
            subfolders_list.extend(subfolder_paths)
    return subfolders_list
    

@app.route('/subfolders', methods=['GET'])
def get_subfolders_route():
    # Return the list of DICOM subfolders stored in the session
    dicom_subfolders = session.get('dicom_subfolders', [])
    segmentation_subfolders = session.get('segmentation_subfolders', [])
    return jsonify({
        'dicom_subfolders': dicom_subfolders,
        'segmentation_subfolders': segmentation_subfolders
    })
 
@app.route('/dicom/<path:filename>')
def serve_dicom_file(filename):
    # Log the received filename for debugging
    print(f"Requested file: {filename}")

    base_dir = os.path.abspath(app.config['EXTRACTED_FOLDER'])
    file_path = safe_join(base_dir, filename)
    print(f"HERERERERERE: {file_path}")

    # Log the absolute file path for debugging
    print(f"Full file path: {file_path}")

    if not os.path.exists(file_path):
        return "File not found", 404
    
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))

@app.route('/segmentation/<path:filename>')
def serve_segmentation_file(filename):
    # Log the received filename for debugging
    print(f"Requested file: {filename}")

    base_dir = os.path.abspath(app.config['SEGMENTED_FOLDER'])
    file_path = safe_join(base_dir, filename)
    
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

@app.route('/list-segmentation-files')
def list_segmentation_files():
    selected_subfolder = request.args.get('subfolder')
    print(f"Requested subfolder: {selected_subfolder}")  # For debugging

    if selected_subfolder is None:
        return jsonify({"error": "No subfolder provided"}), 400
    
    # Ensure the subfolder exists
    subfolder_path = os.path.join(app.config['SEGMENTED_FOLDER'], selected_subfolder)
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

@app.route('/dicom-metadata/<path:filepath>')
def dicom_metadata(filepath):
    # Base directory where DICOM files are stored
    base_dir = os.path.abspath(app.config['EXTRACTED_FOLDER'])
    # Create a secure, absolute file path
    dicom_file_path = safe_join(base_dir, filepath)

    # Ensure the file exists
    if not os.path.exists(dicom_file_path):
        return jsonify({'error': 'File not found'}), 404

    # Extract the metadata from the DICOM file
    ds = pydicom.dcmread(dicom_file_path)

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