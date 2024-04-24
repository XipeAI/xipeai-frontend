import os
import subprocess
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template
from flask_cors import CORS
import zipfile
import shutil
from werkzeug.utils import safe_join
import pydicom
from pydicom.data import get_testdata_files
import secrets
from urllib.parse import unquote
import dicom2nifti


app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5000"])
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted'
SEGMENTED_FOLDER = 'segmented'
SEGMENTED_PP_FOLDER = 'segmented_pp'
NIFTI_FOLDER = 'nifti_extracted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, EXTRACTED_FOLDER)
app.config['SEGMENTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, SEGMENTED_FOLDER)
app.config['SEGMENTED_PP_FOLDER'] = os.path.join(UPLOAD_FOLDER, SEGMENTED_PP_FOLDER)
app.config['NIFTI_FOLDER'] = os.path.join(UPLOAD_FOLDER, NIFTI_FOLDER)
secret_key = secrets.token_urlsafe(24)
app.secret_key = secret_key  
os.environ["CUDA_VISIBLE_DEVICES"] = "4"

# Ensure UPLOAD_FOLDER exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Ensure EXTRACTED_FOLDER exists
os.makedirs(app.config['EXTRACTED_FOLDER'], exist_ok=True)
# Ensure SEGMENTED_FOLDER exists
os.makedirs(app.config['SEGMENTED_FOLDER'], exist_ok=True)
 
# Define the path to your 'src' directory relative to 'app.py'
src_dir = os.path.abspath('src/')


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
 
@app.route('/')
def index():
    # Specify the path and file you want to serve
    return render_template('index.html')
 
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

                # Rename files
                rename_nifti_files(nifti_subfolder_path)
            except Exception as e:
                print(f"Error converting DICOM series in {root}: {e}")
                # Optionally, use `flash(f"Error converting DICOM series in {root}: {e}")` to send feedback to the template


def rename_nifti_files(nifti_subfolder_path):
    for filename in os.listdir(nifti_subfolder_path):
        if filename.endswith('.nii.gz'):

            last_part = nifti_subfolder_path.split('_')[-1]
            # Check if the last part is numeric and pad it
            if last_part.isdigit():
                # Pad the number to three digits
                padded_number = last_part.zfill(3)
            else:
                padded_number = last_part  # Return None or raise an error if the last part is not numeric
            # Formulate the new filename
            new_filename = f"volume_{padded_number}_0000.nii.gz"
            old_file_path = os.path.join(nifti_subfolder_path, filename)
            new_file_path = os.path.join(nifti_subfolder_path, new_filename)
            # Rename the file
            os.rename(old_file_path, new_file_path)
            print(f"Renamed {filename} to {new_filename}")
            break  # Assuming only one NIfTI file is expected per directory

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return {"success": True, "output": result.stdout}  # Success case
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": e.stderr}  # Error case
    
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
        remove_spaces_from_folders(app.config['SEGMENTED_FOLDER'])

        # Get the list of subfolders
        segmentation_subfolders = get_subfolders(app.config['SEGMENTED_FOLDER'])
        session['segmentation_subfolders'] = segmentation_subfolders  # Only update the segmentation subfolders

        return redirect(url_for('index'))
    else:
        return 'Invalid file format or no file selected'

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


@app.route('/run-analysis', methods=['POST'])
def run_analysis():
    subfolder = request.json.get('subfolder')
    
    # construct input folder
    input_folder = os.path.abspath(app.config['NIFTI_FOLDER'])
    input_folder = safe_join(input_folder, subfolder)
    
    # construct output folder
    output_folder = os.path.abspath(app.config['SEGMENTED_FOLDER'])
    output_folder = safe_join(output_folder, subfolder)
    os.makedirs(output_folder, exist_ok=True)
    
    # construct output_pp folder
    output_pp_folder = os.path.abspath(app.config['SEGMENTED_PP_FOLDER'])
    output_pp_folder = safe_join(output_pp_folder, subfolder)
    os.makedirs(output_pp_folder, exist_ok=True)
    
    # Command 1: Predicting with nnUNet
    predict_command = f'nnUNetv2_predict -d Dataset001_Liver -i {input_folder} -o {output_folder} -f 0 1 2 3 4 -tr nnUNetTrainer -c 3d_fullres -p nnUNetPlans'
    prediction_result = run_command(predict_command)
    
    if not prediction_result['success']:
        return jsonify({"success": False, "message": "Prediction failed", "error": prediction_result['error']}), 500

    # Command 2: Applying postprocessing with nnUNet
    postprocess_command = f'nnUNetv2_apply_postprocessing -i {output_folder} -o {output_pp_folder} -pp_pkl_file "/ceph/fabiwolf/xipe/data/nnUnet/nnUnet_results/Dataset001_Liver/nnUNetTrainer__nnUNetPlans__3d_fullres/crossval_results_folds_0_1_2_3_4/postprocessing.pkl" -np 8 -plans_json "/ceph/fabiwolf/xipe/data/nnUnet/nnUnet_results/Dataset001_Liver/nnUNetTrainer__nnUNetPlans__3d_fullres/crossval_results_folds_0_1_2_3_4/plans.json"'
    postprocess_result = run_command(postprocess_command)
    
    if not postprocess_result['success']:
        return jsonify({"success": False, "message": "Postprocessing failed", "error": postprocess_result['error']}), 500

    
    return jsonify({
        "success": True,
        "message": "Analysis completed successfully",
        "prediction_output": prediction_result['output'],
        "postprocessing_output": postprocess_result['output']
    })
    
    
    
    
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')