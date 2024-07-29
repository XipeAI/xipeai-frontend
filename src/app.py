import sys
import os
import io
from io import BytesIO
import logging
from PIL import Image
from skimage.measure import label, regionprops
from PIL import Image, ImageDraw
# Append the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template, send_file
from flask_cors import CORS
import zipfile
import shutil
from werkzeug.utils import safe_join
import pydicom
from pydicom.data import get_testdata_files
from pydicom.dataset import Dataset, FileMetaDataset
import secrets
from urllib.parse import unquote
import dicom2nifti
import utils.format_transformation as utils
from PIL import Image
import base64
from datetime import datetime
import numpy as np
import SimpleITK as sitk
import tempfile
from zipfile import ZipFile
from utils.format_transformation import get_dicom_voxel_dims, calculate_tumor_properties


app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5001"])
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted'
SEGMENTED_FOLDER = 'segmented'
SEGMENTED_PP_FOLDER = 'segmented_pp'
NIFTI_FOLDER = 'nifti_extracted'
SEGMENTED_DICOM = 'segmented_dicom'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, EXTRACTED_FOLDER)
app.config['SEGMENTED_FOLDER'] = os.path.join(UPLOAD_FOLDER, SEGMENTED_FOLDER)
app.config['SEGMENTED_PP_FOLDER'] = os.path.join(UPLOAD_FOLDER, SEGMENTED_PP_FOLDER)
app.config['NIFTI_FOLDER'] = os.path.join(UPLOAD_FOLDER, NIFTI_FOLDER)
app.config['SEGMENTED_DICOM'] = os.path.join(UPLOAD_FOLDER, SEGMENTED_DICOM)
secret_key = secrets.token_urlsafe(24)
app.secret_key = secret_key  
 # os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# Ensure UPLOAD_FOLDER exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Ensure EXTRACTED_FOLDER exists
os.makedirs(app.config['EXTRACTED_FOLDER'], exist_ok=True)
# Ensure SEGMENTED_FOLDER exists
os.makedirs(app.config['SEGMENTED_FOLDER'], exist_ok=True)
# Ensure SEGMENTED_DICOM exists
os.makedirs(app.config['SEGMENTED_DICOM'], exist_ok=True)
# Ensure SEGMENTED_DICOM exists
os.makedirs(app.config['SEGMENTED_PP_FOLDER'], exist_ok=True)
 
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
    logging.info(f"Running command: {command}")
    
    # Split the command to verify input and output paths
    command_parts = command.split()
    input_dir = None
    output_dir = None

    for i, part in enumerate(command_parts):
        if part == '-i' and i + 1 < len(command_parts):
            input_dir = command_parts[i + 1]
        if part == '-o' and i + 1 < len(command_parts):
            output_dir = command_parts[i + 1]

    if input_dir and not os.path.exists(input_dir):
        logging.error(f"Input directory does not exist: {input_dir}")
        return {"success": False, "error": f"Input directory does not exist: {input_dir}"}
    
    if output_dir and not os.path.exists(output_dir):
        logging.error(f"Output directory does not exist: {output_dir}")
        return {"success": False, "error": f"Output directory does not exist: {output_dir}"}
    
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logging.info(f"Command succeeded: {command}")
        logging.debug(f"Command output: {result.stdout}")
        return {"success": True, "output": result.stdout}
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {command}")
        logging.error(f"Return code: {e.returncode}")
        logging.error(f"Error output: {e.stderr}")
        return {"success": False, "error": e.stderr}
    except Exception as e:
        logging.exception(f"An unexpected error occurred while running the command: {command}")
        return {"success": False, "error": str(e)}
    
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

def find_nii_gz_file(directory):
    """ Returns the name of the first .nii.gz file found in the specified directory. """
    for file in os.listdir(directory):
        if file.endswith('.nii.gz'):
            return file
    return None  # Return None if no .nii.gz file is found


        
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
    segmented_dicom_subfolders = session.get('segmented_dicom_subfolders', [])
    return jsonify({
        'dicom_subfolders': dicom_subfolders,
        'segmentation_subfolders': segmentation_subfolders,
        'segmented_dicom_subfolders': segmented_dicom_subfolders
    })
 
@app.route('/dicom/<path:filename>')
def serve_dicom_file(filename):
    # Log the received filename for debugging
    print(f"Requested file: {filename}")

    base_dir = os.path.abspath(app.config['EXTRACTED_FOLDER'])
    file_path = os.path.join(base_dir, filename)
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
    file_path = os.path.join(base_dir, filename)
    
    if not os.path.exists(file_path):
        return "File not found", 404
    
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))

@app.route('/segmented-dicom/<path:filename>')
def serve_segmented_dicom(filename):
    """Serve segmented DICOM files."""
    base_dir = os.path.abspath(app.config['SEGMENTED_DICOM'])
    file_path = os.path.join(base_dir, filename)
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

@app.route('/list-segmented-dicom-files')
def list_segmented_dicom_files():
    selected_subfolder = request.args.get('subfolder')
    print(f"Requested subfolder: {selected_subfolder}")  # For debugging

    if selected_subfolder is None:
        return jsonify({"error": "No subfolder provided"}), 400
    
    # Ensure the subfolder exists
    subfolder_path = os.path.join(app.config['SEGMENTED_DICOM'], selected_subfolder)
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
    dicom_file_path = os.path.join(base_dir, filepath)

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
    input_folder = os.path.join(input_folder, subfolder)

    # construct extracetd folder
    extracted_folder = os.path.abspath(app.config['EXTRACTED_FOLDER'])
    extracted_folder = os.path.join(extracted_folder, subfolder)
    
    # construct output folder
    output_folder = os.path.abspath(app.config['SEGMENTED_FOLDER'])
    print(output_folder)
    print(subfolder)
    output_folder = os.path.join(output_folder, subfolder)
    print(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    
    # construct output_pp folder
    output_pp_folder = os.path.abspath(app.config['SEGMENTED_PP_FOLDER'])
    output_pp_folder = os.path.join(output_pp_folder, subfolder)
    os.makedirs(output_pp_folder, exist_ok=True)
    
    # construct segmented_dicom folder
    segmented_dicom_folder = os.path.abspath(app.config['SEGMENTED_DICOM'])
    segmented_dicom_folder = os.path.join(segmented_dicom_folder, subfolder)
    os.makedirs(segmented_dicom_folder, exist_ok=True)
    
    # Command 1: Predicting with nnUNet
    predict_command = f'nnUNetv2_predict -d Dataset002_Liver -i {input_folder} -o {output_folder} -f 0 1 2 3 4 -tr nnUNetTrainer -c 3d_fullres -p nnUNetPlans'
    prediction_result = run_command(predict_command)
    
    if not prediction_result['success']:
        return jsonify({"success": False, "message": "Prediction failed", "error": prediction_result['error']}), 500

    # Command 2: Applying postprocessing with nnUNet
    postprocess_command = f'nnUNetv2_apply_postprocessing -i {output_folder} -o {output_pp_folder} -pp_pkl_file "C:/MyPythonProjects/XipeAI/models/nnUnet_results/Dataset002_Liver/nnUNetTrainer__nnUNetPlans__3d_fullres/crossval_results_folds_0_1_2_3_4/postprocessing.pkl" -np 8 -plans_json "C:/MyPythonProjects/XipeAI/models/nnUnet_results/Dataset002_Liver/nnUNetTrainer__nnUNetPlans__3d_fullres/crossval_results_folds_0_1_2_3_4/plans.json"'
    postprocess_result = run_command(postprocess_command)
    
    if not postprocess_result['success']:
        return jsonify({"success": False, "message": "Postprocessing failed", "error": postprocess_result['error']}), 500
    
    
    nifti_name = find_nii_gz_file(output_pp_folder)
    if nifti_name:
        input_dir = f"{output_pp_folder}/{nifti_name}"
        utils.nifti2dicom_1file(input_dir, extracted_folder, segmented_dicom_folder)
        
    # Get the list of subfolders
    segmented_dicom_subfolders = get_subfolders(app.config['SEGMENTED_DICOM'])
    session['segmented_dicom_subfolders'] = segmented_dicom_subfolders  # Only update the DICOM subfolders
    
    return jsonify({
        "success": True,
        "message": "Analysis completed successfully",
        "prediction_output": prediction_result['output'],
        "postprocessing_output": postprocess_result['output']
    })

def png_to_grayscale_dcm(image_data, filename):
    # Convert binary data to a PIL image
    image = Image.open(io.BytesIO(image_data)).convert('L')  # Convert to grayscale
    pixel_array = np.array(image)

    # Create a new DICOM dataset
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    file_meta.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID

    # Create the main dataset and set necessary values
    ds = Dataset()
    ds.file_meta = file_meta
    ds.PatientName = "Test^Patient"
    ds.PatientID = "123456"
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.is_little_endian = True
    ds.is_implicit_VR = True

    # Set creation date and time
    dt = datetime.now()
    ds.ContentDate = dt.strftime('%Y%m%d')
    ds.ContentTime = dt.strftime('%H%M%S.%f')  # Long format with microseconds

    # Set necessary DICOM attributes for image data
    ds.Modality = 'OT'
    ds.Rows, ds.Columns = pixel_array.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = pixel_array.tobytes()

    # Save DICOM file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dcm')
    ds.save_as(temp_file.name, write_like_original=False)

    return temp_file.name

def apply_ct_window(img, window_width, window_level):
    # Calculate the rescaled image based on the provided window width and window level
    R = (img - window_level + 0.5 * window_width) / window_width
    # Clamp values to the range [0, 1]
    R[R < 0] = 0
    R[R > 1] = 1
    return R


def get_bounding_boxes(mask, label_value):
    labeled_mask = label(mask == label_value)
    regions = regionprops(labeled_mask)
    boxes = []
    for region in regions:
        min_row, min_col, max_row, max_col = region.bbox
        boxes.append((min_row, min_col, max_row, max_col))
    return boxes

def draw_bounding_boxes(image, boxes, margin=5, thickness=2):
    img_bbox = Image.fromarray((255 * image).astype('uint8')).convert('RGB')
    draw = ImageDraw.Draw(img_bbox)
    for box in boxes:
        top, left, bottom, right = box
        top = max(0, top - margin)
        left = max(0, left - margin)
        bottom = min(image.shape[0], bottom + margin)
        right = min(image.shape[1], right + margin)
        for i in range(thickness):
            draw.rectangle(
                [left + i, top + i, right - i, bottom - i],
                outline=(255, 0, 0)
            )
    del draw
    return np.asarray(img_bbox)

def create_dicom_with_bboxes(dicom_file, segmentation_file, filename, window_width, window_level):
    # Decode the DICOM file data
    ds = pydicom.dcmread(io.BytesIO(dicom_file.read()))
    img = ds.pixel_array.astype(float)
    img = img * ds.RescaleSlope + ds.RescaleIntercept

    # Apply the CT window
    display_img = apply_ct_window(img, window_width, window_level)

    # Decode the segmentation file data
    seg_ds = pydicom.dcmread(io.BytesIO(segmentation_file.read()))
    mask = seg_ds.pixel_array

    # Get bounding boxes for regions labeled as 2
    boxes = get_bounding_boxes(mask, 2)

    # Draw bounding boxes on the image
    img_bbox = draw_bounding_boxes(display_img, boxes)

    # Modify DICOM tags
    ds.PhotometricInterpretation = 'RGB'
    ds.SamplesPerPixel = 3
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.add_new(0x00280006, 'US', 0)
    ds.is_little_endian = True
    ds.fix_meta_info()

    # Save pixel data and DICOM file to an in-memory byte stream
    ds.PixelData = img_bbox.tobytes()
    dicom_bytes = io.BytesIO()
    ds.save_as(dicom_bytes)
    dicom_bytes.seek(0)
    
    return dicom_bytes

def get_summary(filename):
    file_path = os.path.join(app.config["EXTRACTED_FOLDER"], filename)
    
    for file_name in os.listdir(file_path):
        if "_summary" in file_name and file_name.endswith(".dcm"):
            full_path = os.path.join(file_path, file_name)
            # Assuming the file is already a binary DICOM file
            with open(full_path, 'rb') as file:
                return BytesIO(file.read())

@app.route('/api/save_dicom_series', methods=['POST'])
def save_dicom_series():
    # Extract multiple files for dicoms and segmentations
    dicom_files = request.files.getlist('dicomFiles')
    segmentation_files = request.files.getlist('segmentationFiles')

    # Check if any required files are missing
    if not dicom_files or not segmentation_files:
        return jsonify({'error': 'Missing DICOM or segmentation files'}), 400

    # Extract additional parameters from the request
    filename = request.form.get('filename', 'exported_series')
    window_width = float(request.form.get('windowWidth', 150))
    window_level = float(request.form.get('windowLevel', 60))

    # Memory buffer for our ZIP file
    in_memory = BytesIO()

    try:
        with ZipFile(in_memory, mode='w') as zf:
            # Process each DICOM and segmentation pair
            for dicom_file, segmentation_file in zip(dicom_files, segmentation_files):
                processed_data = create_dicom_with_bboxes(dicom_file, segmentation_file, filename, window_width, window_level)
                zf.writestr(f"{filename}_{dicom_file.filename}", processed_data.getvalue())

            # Add an summary DICOM file
            summary = get_summary(filename)
            zf.writestr(f"{filename}_summary.dcm", summary.getvalue())

        # Prepare the zip file to send
        in_memory.seek(0)
        return send_file(
            in_memory,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{filename}.zip',
        )
    except Exception as e:
        print("Exception:", str(e))  # Debugging statement
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/tumors/<path:subfolder>', methods=['GET'])
def get_tumors(subfolder):
    dicom_folder = os.path.join(app.config["EXTRACTED_FOLDER"], subfolder)
    nifti_predicted_folder = os.path.join(app.config["SEGMENTED_PP_FOLDER"], subfolder)

    voxel_dims = get_dicom_voxel_dims(dicom_folder)

    # Read the NIfTI file
    if os.path.exists(nifti_predicted_folder):
        for file in os.listdir(nifti_predicted_folder):
            if file.endswith('.nii') or file.endswith('.nii.gz'):
                file_path = os.path.join(nifti_predicted_folder, file)

            new_img = sitk.ReadImage(file_path)

            # Convert the image to an integer type if necessary
            if new_img.GetPixelID() in [sitk.sitkFloat32, sitk.sitkFloat64]:
                new_img = sitk.Cast(new_img, sitk.sitkInt16)

            tumor_properties = calculate_tumor_properties(new_img, voxel_dims)

            print(tumor_properties)

            return jsonify(tumor_properties)

    return []

    
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)