import cv2
import os
from os import listdir
from os.path import isfile, join

def extract_subfigures(image_folder, image_filename, output_dir="extracted_panels"):
    """
    Extract Figure using image path and output to the output directory which is default to the extracted_panels folder
    
    Args: 
        image_path: full image file path
        image_filename: file name of the image
        output_dir: output directory path

    Returns:
        image saved at output directory with naming rule image_file_name + panel + index of the panel

    Examples:
        extract_subfigures("./image_folder", "image_1", "./result")
    """
    # 1. Load the image
    image_path = join(image_folder, image_filename)
    if not os.path.exists(image_path):
        print(f"Error: File {image_path} not found.")
        return

    img = cv2.imread(image_path)
    original = img.copy()
    
    # 2. Preprocessing
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Thresholding: Convert to pure black and white
    # OTSU automatically finds the best threshold value
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 3. Morphological Operations
    # Create a rectangular kernel. 
    # Increase these numbers (e.g., 20, 20) if your figure is breaking into small pieces.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    
    # Dilation connects nearby white pixels into a single blob
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    # 4. Find Contours
    # RETR_EXTERNAL gets only the outer boundaries
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 5. Filter and Sort Contours
    bounding_boxes = []
    
    img_area = img.shape[0] * img.shape[1]
    min_area = img_area * 0.05  # Filter: Box must be at least 5% of total image area

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        
        if area > min_area:
            bounding_boxes.append((x, y, w, h))

    # Sort boxes from Left to Right
    bounding_boxes = sorted(bounding_boxes, key=lambda box: box[0])

    print(f"Found {len(bounding_boxes)} panels.")

    # 6. Crop and Save
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, (x, y, w, h) in enumerate(bounding_boxes):
        # Add padding
        pad = 5
        x_pad = max(0, x - pad)
        y_pad = max(0, y - pad)
        w_pad = min(img.shape[1] - x_pad, w + 2*pad)
        h_pad = min(img.shape[0] - y_pad, h + 2*pad)

        # Crop
        roi = original[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad]
        
        # Save
        filename = f"{output_dir}/{image_filename}_panel_{i+1}.jpg"
        cv2.imwrite(filename, roi)


def extract_all_subfigures(data_dir, output_dir):
    """
    Extract Figures for all image in the data directory and output to the output directory

    Args: 
        data_dir: data directory path 
        output_dir: output directory path name
    
    Returns:
        image saved at output directory with naming rule image_file_name + panel + index of the panel

    Examples:
        extract_all_subfigures("./image_folder", "./result")
    """
    #data_dir = os.path.join(data_dir, '/SEM')
    image_files = [f for f in listdir(data_dir) if isfile(join(data_dir, f))]
    for i in range(len(image_files)):
        extract_subfigures(data_dir, image_files[i], output_dir)