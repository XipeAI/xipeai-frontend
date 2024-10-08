function updateFileName(input) {
    document.getElementById('file-name').textContent = input.files.length > 0 ? input.files[0].name : 'No file chosen';
}

function updateSegmentationName(input) {
    document.getElementById('segmentation-name').textContent = input.files.length > 0 ? input.files[0].name : 'No file chosen';
}

function applyWindowing() {
        const element = document.getElementById('dicomViewer');
        const viewport = cornerstone.getViewport(element);

        // Retrieve the window width and window level from the input sliders
        const windowWidth = document.getElementById('window-width').value;
        const windowLevel = document.getElementById('window-level').value;

        // Apply the windowing parameters
        viewport.voi.windowWidth = parseInt(windowWidth, 10);
        viewport.voi.windowCenter = parseInt(windowLevel, 10);

        // Update the viewport with the new settings
        cornerstone.setViewport(element, viewport);
    }

function exportCanvasAsImage(dicomViewerElement, filename) {
    const cornerstoneCanvas = $(dicomViewerElement).find('canvas').get(0);
    if (cornerstoneCanvas) {
        // Convert the canvas to a Data URL
        const imageDataUrl = cornerstoneCanvas.toDataURL('image/png');

        // Create a temporary download link
        const downloadLink = document.createElement('a');
        downloadLink.href = imageDataUrl;
        downloadLink.download = filename || 'exported-image.png'; // You can specify a default filename

        // Append the link to the body, click it, and then remove it
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
    } else {
        console.error('DICOM Viewer canvas not found for export.');
    }
}
    

$(document).ready(function() {
    let currentIndex = 0;
    let dicomFiles = [];
    const element = document.getElementById('dicomViewer');
    cornerstone.enable(element);
    let segmentationFiles = [];
    let lastSegmentationCanvas = null;
    let showBoundingBox = false;
    let showColoredSegmentation = false

    // Button click handlers
    $('#toggle-segmentation').change(function() {
        if ($(this).is(':checked')) {
            // If toggle is on, show bounding box segmentation
            showBoundingBox = true;
            showColoredSegmentation = false;
        } else {
            // If toggle is off, show colored segmentation
            showBoundingBox = false;
            showColoredSegmentation = true;
        }
        updateSegmentationDisplay(); // Update the display
    });

    function exportAllDICOMs() {
        const subfolder = $('#subfolder-select').val();
    
        // Create a FormData object to hold all the DICOM and segmentation files
        const formData = new FormData();
    
        // Append filename and window settings once since they are common for all files
        formData.append('filename', subfolder || 'exported_series');
        const windowWidth = parseInt(document.getElementById('window-width').value, 10);
        const windowLevel = parseInt(document.getElementById('window-level').value, 10);
        formData.append('windowWidth', windowWidth);
        formData.append('windowLevel', windowLevel);
    
        const fileFetchPromises = [];
    
        // Loop through all DICOM files and corresponding segmentation files
        for (let i = 0; i < (dicomFiles.length - 1); i++) {
            const dicomFileName = dicomFiles[i];
            const segmentationFileName = segmentationFiles[i];
            const dicomFileUrl = `/dicom/${subfolder}/${dicomFileName}`;
            const segmentationFileUrl = `/segmented-dicom/${subfolder}/${segmentationFileName}`;
    
            // Fetch each file and append to formData
            fileFetchPromises.push(
                fetch(dicomFileUrl).then(response => response.blob()).then(blob => {
                    formData.append('dicomFiles', blob, dicomFileName);
                })
            );
    
            fileFetchPromises.push(
                fetch(segmentationFileUrl).then(response => response.blob()).then(blob => {
                    formData.append('segmentationFiles', blob, segmentationFileName);
                })
            );
        }
    
        // Wait for all files to be fetched and appended
        Promise.all(fileFetchPromises).then(() => {
            // Send the FormData with all files to the server
            fetch('/api/save_dicom_series', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.error); });
                }
                return response.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const downloadLink = document.createElement('a');
                downloadLink.href = url;
                downloadLink.download = `${subfolder || 'exported_series'}.zip`;
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
                window.URL.revokeObjectURL(url);
            })
            .catch(error => console.error('Error:', error));
        });
    }
    
    
    
    $('#exportButton').click(function() {
        exportAllDICOMs();
    });

        function updateSegmentationDisplay() {
            // Clear any previously shown segmentation
            clearSegmentationDisplay();

            if (showBoundingBox) {
                loadAndOverlaySegmentationWithBoundingBoxes(currentIndex);
            } else if (showColoredSegmentation) {
                loadAndOverlaySegmentation(currentIndex);
            }
            // This logic assumes that 'else if' is used to ensure only one type of segmentation is shown at a time based on the last selected option. 
            // Adjust this logic based on how you want these toggles to work together.
        }

        function clearSegmentationDisplay() {
            if (lastSegmentationCanvas) {
                // Example: clear the last segmentation canvas if applicable
                const ctx = lastSegmentationCanvas.getContext('2d');
                ctx.clearRect(0, 0, lastSegmentationCanvas.width, lastSegmentationCanvas.height);
                lastSegmentationCanvas = null; // Reset the reference
            }
            // Additional clearing logic here if needed
        }

    // Listen for image rendered events to redraw the last segmentation
    $(element).on('cornerstoneimagerendered', function() {
        if (lastSegmentationCanvas) {
            overlaySegmentationOnDicomViewer(element, lastSegmentationCanvas);
        }
    });


    function loadDicomImagesForSubfolder(subfolder) {
        $.getJSON(`/list-dicom-files?subfolder=${subfolder}`, function(files) {
            dicomFiles = files;
            if (dicomFiles.length > 0) {
                // Use the first file as an example, you can modify this index
                const middleIndex = Math.floor(dicomFiles.length / 2);
                loadDicomImage(middleIndex); // Load the first DICOM file in the viewer
                updateSlider(dicomFiles.length, middleIndex); // Update the slider with the number of files
            } else {
                console.log("No DICOM files found in the selected subfolder.");
                clearViewerAndMetadata();
            }
        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.error("Failed to load DICOM files list for the selected subfolder:", textStatus, errorThrown);
            clearViewerAndMetadata();
        });
    }

    function loadSegmentationImagesForSubfolder(subfolder) {
        $.getJSON(`/list-segmented-dicom-files?subfolder=${encodeURIComponent(subfolder)}`, function(files) {
            segmentationFiles = files;
            if(segmentationFiles.length === 0) {
                console.log("No segmentation files found in the selected subfolder.");
            }
        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.error("Failed to load segmentation files list for the selected subfolder:", textStatus, errorThrown);
        });
    }

    function updateSlider(numFiles, middleIndex) {
        const slider = document.getElementById('dicom-slider');
        slider.max = numFiles - 1;
        slider.value = middleIndex; // Set slider to the middle index
        showSliderValue(); // Update the slider's displayed value
    }


    function clearViewerAndMetadata() {
        // Clear the DICOM viewer and metadata table
        document.getElementById('dicomViewer').textContent = ''; // Or clear the viewer in the way appropriate for your DICOM library
        const table = document.getElementById('dicom-metadata-table');
        table.innerHTML = '<tr><th>Field</th><th>Value</th></tr>'; // Reset the table to just the headers
        var rangeBullet = document.getElementById("rs-bullet");
        rangeBullet.innerHTML = '0 / 0'; // Reset the range label
    }

    function loadDicomImage(imageIndex) {
        if (dicomFiles.length === 0) return;

        imageIndex = Math.max(0, Math.min(imageIndex, dicomFiles.length - 1));
        const subfolder = $('#subfolder-select').val(); 
        const filename = dicomFiles[imageIndex];
        const imageId = `wadouri:http://127.0.0.1:5001/dicom/${subfolder}/${filename}`;

        cornerstone.loadImage(imageId).then(function(image) {
            cornerstone.displayImage(element, image);
            applyWindowing()
            updateSegmentationDisplay();
            fetchAndDisplayMetadata(subfolder + '/' + filename); // Fetch and display metadata for the loaded image
        }).catch(function(error) {
            console.error('Error loading DICOM image:', error);
        });

        currentIndex = imageIndex; // Update the current index
        showSliderValue(); // Call to update the slider's display
    }

    function loadAndOverlaySegmentation(imageIndex) {
        if (segmentationFiles.length > imageIndex) {
            const subfolder = $('#subfolder-select').val(); 
            const filename = segmentationFiles[imageIndex];
            const segmentationImageId = `wadouri:http://127.0.0.1:5001/segmented-dicom/${subfolder}/${filename}`;
            cornerstone.loadImage(segmentationImageId).then(function(segmentationImage) {
                const pixelData = segmentationImage.getPixelData();
                
                const canvas = document.createElement('canvas');
                canvas.width = segmentationImage.width;
                canvas.height = segmentationImage.height;
                const context = canvas.getContext('2d');
                
                const imageData = context.createImageData(canvas.width, canvas.height);
                const data = imageData.data;

                for (let i = 0; i < pixelData.length; i++) {
                    const index = i * 4; 
                    if (pixelData[i] === 1) { // Liver, for example
                        data[index] = 0;
                        data[index + 1] = 255;
                        data[index + 2] = 0;
                        data[index + 3] = 128; // Semi-transparent
                    } else if (pixelData[i] === 2) { // Tumor, for example
                        data[index] = 255;
                        data[index + 1] = 0;
                        data[index + 2] = 0;
                        data[index + 3] = 128; // Semi-transparent
                    }
                }

                context.putImageData(imageData, 0, 0);
                lastSegmentationCanvas = canvas;
                overlaySegmentationOnDicomViewer(element, canvas);
            }).catch(function(error) {
                console.error('Error loading segmentation image:', error);
            });
        }
    }


    function labelConnectedComponents(pixelData, width, height) {
        let labels = new Array(pixelData.length).fill(0);
        let nextLabel = 1;

        // Check if pixel at (x, y) is valid and belongs to a tumor (value 2)
        function isValidAndUnlabeled(x, y) {
            if (x < 0 || x >= width || y < 0 || y >= height) return false;
            const index = y * width + x;
            return pixelData[index] === 2 && labels[index] === 0;
        }

        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                if (!isValidAndUnlabeled(x, y)) continue;

                // Start a new region
                labels[y * width + x] = nextLabel;
                const stack = [[x, y]];

                while (stack.length > 0) {
                    const [cx, cy] = stack.pop();
                    // Check all 4 neighbors
                    [[cx - 1, cy], [cx + 1, cy], [cx, cy - 1], [cx, cy + 1]].forEach(([nx, ny]) => {
                        if (isValidAndUnlabeled(nx, ny)) {
                            labels[ny * width + nx] = nextLabel;
                            stack.push([nx, ny]);
                        }
                    });
                }

                nextLabel++;
            }
        }

        return labels;
    }
    

    //andra boxing

    function boxesAreClose(box1, box2) {
        const threshold = 10; // Adjust this threshold to control the merging sensitivity
        const closeHorizontally = box2.minX <= box1.maxX + threshold && box1.minX <= box2.maxX + threshold;
        const closeVertically = box2.minY <= box1.maxY + threshold && box1.minY <= box2.maxY + threshold;
        return closeHorizontally && closeVertically;
    }

    function mergeOverlappingBoundingBoxes(boundingBoxes) {
        console.log("Initial boundingBoxes:", boundingBoxes);  // Check initial boxes
    
        let mergedBoxes = [];
        boundingBoxes.forEach((box, index) => {
            if (!box) return;
            let merged = false;
            mergedBoxes.forEach(mergedBox => {
                if (boxesAreClose(mergedBox, box)) {
                    mergedBox.minX = Math.min(mergedBox.minX, box.minX);
                    mergedBox.minY = Math.min(mergedBox.minY, box.minY);
                    mergedBox.maxX = Math.max(mergedBox.maxX, box.maxX);
                    mergedBox.maxY = Math.max(mergedBox.maxY, box.maxY);
                    merged = true;
                }
            });
            if (!merged) {
                mergedBoxes.push({...box});
            }
        });
    
        console.log("Merged boundingBoxes:", mergedBoxes);  // Check merged boxes
        return mergedBoxes;
    }

    function updateBoundingBoxesWithMerging(boundingBoxes) {
        const mergedBoxes = mergeOverlappingBoundingBoxes(boundingBoxes);
        // Clear the original array
        boundingBoxes.length = 0;
        // Push the merged boxes into the original array
        mergedBoxes.forEach(box => boundingBoxes.push(box));

        return mergedBoxes;
    }

    function loadAndOverlaySegmentationWithBoundingBoxes(imageIndex) {
        if (segmentationFiles.length > imageIndex) {
            const subfolder = $('#subfolder-select').val();
            const filename = segmentationFiles[imageIndex];
            // Check if '_summary' is in the filename
            if (filename.includes('_summary')) {
                console.log("Skipping file as it contains '_summary': ", filename);
                return; // Skip this file
            }
            const segmentationImageId = `wadouri:http://127.0.0.1:5001/segmented-dicom/${subfolder}/${filename}`;
            cornerstone.loadImage(segmentationImageId).then(function(segmentationImage) {
                const pixelData = segmentationImage.getPixelData();
                const { width, height } = segmentationImage;
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const context = canvas.getContext('2d');
    
                const labels = labelConnectedComponents(pixelData, width, height);
                const boundingBoxes = calculateBoundingBoxes(labels, width, height);
                const mergedBoxes = updateBoundingBoxesWithMerging(boundingBoxes);
    
                // Define margin size (e.g., 5 pixels)
                const margin = 5;
    
                // Draw bounding boxes with margin
                context.strokeStyle = 'red';
                context.lineWidth = 2;
                mergedBoxes.forEach((box) => {
                    if (box) {
                        context.strokeRect(
                            Math.max(box.minX - margin, 0),
                            Math.max(box.minY - margin, 0),
                            Math.min(box.maxX - box.minX + 1 + 2 * margin, width - (box.minX - margin)),
                            Math.min(box.maxY - box.minY + 1 + 2 * margin, height - (box.minY - margin))
                        );
                    }
                });
    
                lastSegmentationCanvas = canvas;
                overlaySegmentationOnDicomViewer(element, canvas);
    
            }).catch(function(error) {
                console.error('Error loading segmentation image:', error);
            });
        }
    }
    

    function calculateBoundingBoxes(labels, width, height) {
        let boundingBoxes = [];
        for (let i = 0; i < labels.length; i++) {
            const label = labels[i];
            if (label === 0) continue; // Skip background pixels

            const x = i % width;
            const y = Math.floor(i / width);

            if (!boundingBoxes[label]) {
                boundingBoxes[label] = { minX: x, minY: y, maxX: x, maxY: y };
            } else {
                let box = boundingBoxes[label];
                box.minX = Math.min(box.minX, x);
                box.minY = Math.min(box.minY, y);
                box.maxX = Math.max(box.maxX, x);
                box.maxY = Math.max(box.maxY, y);
            }
        }
        return boundingBoxes;
    }

    function overlaySegmentationOnDicomViewer(dicomViewerElement, segmentationCanvas) {
        const cornerstoneCanvas = $(dicomViewerElement).find('canvas').get(0);
        if (cornerstoneCanvas) {
            const ctx = cornerstoneCanvas.getContext('2d');
            ctx.drawImage(segmentationCanvas, 0, 0);
            cornerstone.updateImage(dicomViewerElement);
        } else {
            console.error('DICOM Viewer canvas not found.');
        }
    }
    

    function populateMetadataTable(metadata) {
         const table = document.getElementById('dicom-metadata-table');
         table.innerHTML = '<tr><th>Field</th><th>Value</th></tr>'; // Reset table


    function updateProgressBar(currentIndex, totalFiles) {
        const progressPercentage = (currentIndex / totalFiles) * 100;
        document.getElementById('progress-bar').style.width = `${progressPercentage}%`;
    }

    
    function formatBirthDate(dateString) {
        if (dateString && dateString.length === 8) {
            return dateString.substring(0, 4) + '-' + dateString.substring(4, 6) + '-' + dateString.substring(6, 8);
        }
        return dateString;
    }

    // Populate the table with metadata or random dummy data if 'NA'
    metadata.forEach(function(fieldInfo) {
        const row = table.insertRow(-1);
        const cellField = row.insertCell(0);
        const cellValue = row.insertCell(1);
        cellField.textContent = fieldInfo['Field'];
        
        // Use provided value, or fetch dummy data if 'NA'
        let value = fieldInfo['Value'] !== 'NA' ? fieldInfo['Value'] : getRandomData(fieldInfo['Field']);
        cellValue.textContent = value;
    });
    }

    function getRandomData(field) {
        // Define your dummy data for each field or return a general placeholder
        const dummyData = {
            'Patient Name': 'John Doe',
            'Patient Birth Date': '1980-01-01',
            'Body Part Examined': 'Head',
            'Study Time': '14:30:00',
            'Accession Number': '123456789',
            'Modality': 'CT',
            'Result': 'N/A',
            'Study Description': 'Routine checkup',
            // Add more fields as necessary
        };

        return dummyData[field] || 'Not Available'; // Return specific dummy data or a general placeholder
    }

    function fetchAndDisplayMetadata(fullPath) {
        // Building the URL by including the subfolder path
        const url = `/dicom-metadata/${fullPath}`;
    
        $.getJSON(url, function(metadata) {
            populateMetadataTable(metadata);
        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.error("Failed to load DICOM metadata:", textStatus, errorThrown);
        });
    }


    // Fetch the list of DICOM files
    $.getJSON('/list-dicom-files', function(files) {
        dicomFiles = files;
        if (dicomFiles.length > 0) {
            // Calculate the initial index to start at the middle of the DICOM files list
            const initialIndex = Math.floor(dicomFiles.length / 2);

            const slider = document.getElementById('dicom-slider');
            slider.max = dicomFiles.length - 1;
            slider.value = initialIndex; // Set slider position to the middle

            // Load the DICOM image at the initial index (middle of the list)
            loadDicomImage(initialIndex);

            // Set the initial value display
            showSliderValue(); // <-- This is the new position of the call

            slider.addEventListener('input', function() {
                loadDicomImage(parseInt(this.value, 10));
                showSliderValue(); 
            });
        }   else {
            // Handle the case where there are no DICOM files
            rangeBullet.innerHTML = '0 / 0';
        }
    });

    // Fetch the list of segmentation files
    $.getJSON('/list-segmentation-files', function(files) {
        segmentationFiles = files;
        // if (segmentationFiles.length > 0) {
        //     loadSegmentationImage(0); // Load the first segmentation image
            
        // }
    });

    // Slider event listener
    const slider = document.getElementById('dicom-slider');
    // Slider event listener
    slider.addEventListener('input', function(e) {
        const index = parseInt(e.target.value, 10);
        currentIndex = index;
        loadDicomImage(index);
        updateProgressBar(currentIndex, dicomFiles.length); // Updated to call with the correct parameters
        // Calculate the initial index to start at the middle of the DICOM files list
        const initialIndex = Math.floor(dicomFiles.length / 2);

        const slider = document.getElementById('dicom-slider');
        slider.max = dicomFiles.length - 1;
        slider.value = initialIndex; // Set slider position to the middle

        // Load the DICOM image at the initial index (middle of the list)
        loadDicomImage(initialIndex);

        // Set the initial value display
        showSliderValue(); // <-- This is the new position of the call

    });


    function updateProgressBar(currentIndex, totalFiles) {
        // Adjusted to account for zero-based indexing; ensures the first image shows some progress and the last image fills the bar
        const progressPercentage = ((currentIndex + 1) / totalFiles) * 100;
        document.getElementById('progress-bar').style.width = `${progressPercentage}%`;
    }
    

    $(element).on('mousewheel DOMMouseScroll', function(e) {
        e.preventDefault(); // Prevent the default scroll behavior

        const direction = e.originalEvent.wheelDelta || -e.originalEvent.detail;
        let newIndex = currentIndex + (direction > 0 ? -1 : 1); // Calculate new index based on scroll direction

        // Ensure newIndex stays within the bounds of available DICOM files
        newIndex = Math.max(0, Math.min(newIndex, dicomFiles.length - 1));

        if (newIndex !== currentIndex) { // Check if the index has actually changed
            loadDicomImage(newIndex); // Load and display the new DICOM image

            // Synchronize the slider with the current DICOM image being displayed
            const slider = document.getElementById('dicom-slider');
            slider.value = newIndex; // Update the slider's position

            currentIndex = newIndex; // Update the global currentIndex to the new value
            showSliderValue(); // Optionally, update any display elements showing the current slider value
        }
    });


    // function updateProgressBar() {
    //     const progressBar = document.getElementById('progress-bar');
    //     const percentage = (currentIndex / (dicomFiles.length - 1)) * 100;
    //     progressBar.style.width = percentage + '%';
    // }

    var rangeSlider = document.getElementById("dicom-slider");
    var rangeBullet = document.getElementById("rs-bullet");

    function showSliderValue() {
        var value = parseInt(rangeSlider.value); // Get the current value of the slider
        var max = parseInt(rangeSlider.max); // Get the maximum value of the slider

        // Update the bullet with the current value and the total number of DICOM files
        rangeBullet.innerHTML = (value) + '/' + dicomFiles.length; // Display starts from 1

        // Calculate the bullet's position as a percentage
        var percent = ((value - rangeSlider.min) / (max - rangeSlider.min));

        // Thumb width adjustment logic
        var thumbWidth = -11; // Adjust as needed to match your slider's thumb width

        // Calculate the new position for the bullet, including the thumbWidth adjustment
        var bulletPosition = (percent * (rangeSlider.offsetWidth + thumbWidth)) + (thumbWidth / 2);

        // Update the position of the bullet relative to the slider
        rangeBullet.style.left = `calc(${bulletPosition}px + (${thumbWidth / 2}px))`; // Adjusted to include thumbWidth in calculation
    }

    function checkAndEnableAnalyseButton(subfolder) {
        if (subfolder) {
            $.getJSON(`/list-dicom-files?subfolder=${encodeURIComponent(subfolder)}`, function(files) {
                if (files && files.length > 0) {
                    // DICOM files are present, enable the Analyse button
                    $('#analyse-btn').prop('disabled', false).css({cursor: 'pointer', opacity: 1});
                } else {
                    // No DICOM files found, disable the Analyse button
                    $('#analyse-btn').prop('disabled', true).css({cursor: 'not-allowed', opacity: 0.5});
                }
            }).fail(function() {
                // Request failed, disable the Analyse button
                $('#analyse-btn').prop('disabled', true).css({cursor: 'not-allowed', opacity: 0.5});
            });
        } else {
            // No subfolder is selected, disable the Analyse button
            $('#analyse-btn').prop('disabled', true).css({cursor: 'not-allowed', opacity: 0.5});
        }
    }
    

    // Add the event listener to update the value display on input
    rangeSlider.addEventListener('input', function() {
        const newIndex = parseInt(this.value, 10);
        loadDicomImage(newIndex);
        showSliderValue();
    });

    $('#dicom-slider').on('input', function() {
        loadDicomImage(parseInt(this.value, 10));
    });

    $('#subfolder-select').change(function() {
        const selectedSubfolder = $(this).val();
        loadDicomImagesForSubfolder(selectedSubfolder);// Trigger loading DICOM files for the selected subfolder
        loadSegmentationImagesForSubfolder(selectedSubfolder);
        checkAndEnableAnalyseButton(selectedSubfolder);
        createTumorTable(selectedSubfolder);
    });

    function createTumorTable(selectedSubfolder) {
        console.log('we are in tumor-table')
        fetch(`/api/tumors/${selectedSubfolder}`)
            .then(response => response.json())
            .then(data => {
                const table = document.getElementById('tumor-table');
                const tbody = table.getElementsByTagName('tbody')[0] || table.appendChild(document.createElement('tbody'));
                tbody.innerHTML = ''; // Clear previous entries
    
                // Insert new data
                data.forEach(tumor => {
                    let row = tbody.insertRow();
                    row.insertCell(0).innerHTML = tumor['Tumor ID'];
                    row.insertCell(1).innerHTML = tumor['Width (mm)'];
                    row.insertCell(2).innerHTML = tumor['Height (mm)'];
                    row.insertCell(3).innerHTML = tumor['Length (mm)'];
                    row.insertCell(4).innerHTML = tumor['Volume (cubic mm)'];
                });
            })
            .catch(error => console.error('Error:', error));
    }

    $.getJSON('/subfolders', function(data) {
        const dicomSubfolderSelect = document.getElementById('subfolder-select');
        data.dicom_subfolders.forEach(function(subfolder) {
            const option = document.createElement('option');
            option.value = subfolder;
            option.textContent = subfolder;
            dicomSubfolderSelect.appendChild(option);
        });

        const segmentationSubfolderSelect = document.getElementById('segmentation-subfolder-select');
        data.segmentation_subfolders.forEach(function(subfolder) {
            const option = document.createElement('option');
            option.value = subfolder;
            option.textContent = subfolder;
            segmentationSubfolderSelect.appendChild(option);
        });
    });

    
    
    // Event listener for the Analyse button
    $('#analyse-btn').click(function() {
        var selectedSubfolder = $('#subfolder-select').val();

        // Show the loading screen when the analysis starts
        $('#analyse-screen').show();

        $.ajax({
            url: '/run-analysis',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({subfolder: selectedSubfolder}),
            success: function(response) {
                console.log('Analysis completed: ', response.message);
                if (response.output) {
                    console.log('Analysis Output: ', response.output);
                }

                // Hide the loading screen whether success or failure
                $('#analyse-screen').hide();

                // After hiding the loading screen, check if a subfolder is selected and load segmentation images
                if (selectedSubfolder) {
                    loadSegmentationImagesForSubfolder(selectedSubfolder);
                } else {
                    alert("Please select a segmentation subfolder first.");
                }
            },
            error: function(xhr) {
                console.error('Analysis failed: ', xhr.responseJSON.error);

                // Hide the loading screen on error as well
                $('#analyse-screen').hide();

                // Optionally, display an alert or another form of error message to the user
                alert("Analysis failed: " + xhr.responseJSON.error);
            }
        });
    });

    $('#analyse-segmentation-btn').click(function() {
        var selectedSubfolder = $('#segmentation-subfolder-select').val();
        if (selectedSubfolder) {
            // Load and display segmentation images or perform necessary analysis
            // This function needs to be defined or updated to handle segmentation files
            loadSegmentationImagesForSubfolder(selectedSubfolder); 
        } else {
            alert("Please select a segmentation subfolder first.");
        }
    });

    // Trigger the loading screen on form submission
    $('form').submit(function(event) {
        $('#loading-screen').show();
    });

    // Assuming you're using AJAX to handle the form submission:
    $('form').on('submit', function(e) {
        e.preventDefault();  // Prevent the default form submission
        var formData = new FormData(this);

        $.ajax({
            url: $(this).attr('action'),
            type: 'POST',
            data: formData,
            contentType: false,
            processData: false,
            success: function(data) {
                console.log('Upload successful');
                $('#loading-screen').hide();
                // Handle success
                location.reload();
            },
            error: function(data) {
                console.error('Upload failed');
                $('#loading-screen').hide();
                // Handle error
                location.reload();
            }
        });
    });
});