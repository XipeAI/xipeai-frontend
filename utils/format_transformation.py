import SimpleITK as sitk
import os
import time
from glob import glob
from werkzeug.utils import safe_join


def writeSlices(series_tag_values, new_img, i, out_dir, total_slices):
    # Flipping the index to reverse the slice order
    flipped_i = total_slices - 1 - i
    image_slice = new_img[:,:,flipped_i]

    # Flip the image slice vertically
    image_slice = sitk.Flip(image_slice, [False, True, False])

    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    # Tags shared by the series.
    list(map(lambda tag_value: image_slice.SetMetaData(tag_value[0], tag_value[1]), series_tag_values))

    # Slice specific tags.
    image_slice.SetMetaData("0008|0012", time.strftime("%Y%m%d")) # Instance Creation Date
    image_slice.SetMetaData("0008|0013", time.strftime("%H%M%S")) # Instance Creation Time
    image_slice.SetMetaData("0008|0060", "CT")  # Set the type to CT
    image_slice.SetMetaData("0020|0032", '\\'.join(map(str,new_img.TransformIndexToPhysicalPoint((0,0,flipped_i))))) # Image Position (Patient)
    image_slice.SetMetaData("0020|0013", str(i + 1)) # Instance Number

    # Write to the output directory and add the extension dcm, to force writing in DICOM format.
    writer.SetFileName(os.path.join(out_dir, 'slice' + str(i+1).zfill(4) + '.dcm'))
    writer.Execute(image_slice)

def nifti2dicom_1file(in_dir, out_dir):
    """
    This function converts only one nifti file into a DICOM series.
    Flips the slices so the top becomes the bottom and bottom becomes the top.
    """

    os.makedirs(out_dir, exist_ok=True)

    # Read the NIfTI file
    new_img = sitk.ReadImage(in_dir)

    # Convert the image to an integer type if necessary
    if new_img.GetPixelID() in [sitk.sitkFloat32, sitk.sitkFloat64]:
        new_img = sitk.Cast(new_img, sitk.sitkInt16)

    modification_time = time.strftime("%H%M%S")
    modification_date = time.strftime("%Y%m%d")

    direction = new_img.GetDirection()
    series_tag_values = [("0008|0031", modification_time),  # Series Time
                         ("0008|0021", modification_date),  # Series Date
                         ("0008|0008", "DERIVED\\SECONDARY"),  # Image Type
                         ("0020|000e", "1.2.826.0.1.3680043.2.1125." + modification_date + ".1" + modification_time),  # Series Instance UID
                         ("0020|0037", '\\'.join(map(str, (direction[0], direction[3], direction[6],
                                                          direction[1], direction[4], direction[7])))),
                         ("0008|103e", "Created-Pycad")]  # Series Description

    # Write slices to the output directory, flipping them along the z-axis
    total_slices = new_img.GetDepth()
    list(map(lambda i: writeSlices(series_tag_values, new_img, i, out_dir, total_slices), range(total_slices)))



def nifti2dicom_mfiles(nifti_dir, out_dir=''):
    """
    This function converts multiple .nii files located in a specified directory into DICOM files.

    Parameters:
    - nifti_dir: The directory containing the .nii files.
    - out_dir: The directory where the converted DICOM files will be saved.

    Each .nii file's DICOMs will be stored in a separate subdirectory within out_dir, named after the .nii file.
    """

    # Adjust the pattern to match .nii files
    nifti_files = glob(os.path.join(nifti_dir, '*.nii.gz'))

    for nifti_file in nifti_files:
        # Extract the base name of the nifti file to use as a subdirectory name for the DICOM files
        base_name = os.path.basename(nifti_file)[:-4]  # Remove the '.nii' extension
        dicom_subdir = os.path.join(out_dir, base_name)
        
        # Ensure the output directory exists
        os.makedirs(dicom_subdir, exist_ok=True)

        # Call the conversion function on each nifti file
        nifti2dicom_1file(nifti_file, dicom_subdir)

# if __name__ == "__main__":
    # # add here your conversions you want to do
    # input_dir = '/Users/fabio22/Iwas/Xipe_Data/nifti/segmentations/segmentation-0.nii'
    # output_dir = '/Users/fabio22/Iwas/Xipe_Data/dicom/segmentations'

    # nifti2dicom_1file(input_dir, output_dir)

    