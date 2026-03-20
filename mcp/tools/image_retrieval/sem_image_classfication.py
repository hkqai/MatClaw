import torch
import timm
from timm.data import resolve_data_config
from timm.data.transforms_factory import create_transform
import os
from os import listdir
from os.path import isfile, join
import wget
from pathlib import Path

from PIL import Image
import shutil
import torch.nn.functional as F
CLASS_NAMES = ['NONSEM', 'SEM']

def download_with_python_wget(url, output_dir="."):
    print(f"Downloading from {url}...")
    
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # wget.download returns the filename it saved to
        filename = wget.download(url, out=output_dir)
        print(f"\nSuccessfully downloaded to: {filename}")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

url = "https://github.com/VCERS/MatClaw/releases/download/v0.0.1/convnextv2_base-finetuned-sem-classifier.pth"
MODEL_NAME = 'convnextv2_base.fcmae_ft_in22k_in1k'
MODEL_PATH = './models/convnextv2_base-finetuned-sem-classifier.pth'
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_model():
    """load model"""
    print(f"Loading model: {MODEL_NAME}...")
    if not os.path.isfile(MODEL_PATH):
        download_with_python_wget(url, output_dir="./models")
    # 1. Create the model architecture
    model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=len(CLASS_NAMES))
    
    # 2. Load the trained weights
    # map_location ensures it loads on CPU if you don't have a GPU right now
    checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
    model.load_state_dict(checkpoint)
    
    model = model.to(DEVICE)
    model.eval() # Set to evaluation mode (turns off Dropout, Batchnorm updates)
    return model

def get_transform(model):
    """Get the exact transforms (resize/normalize) required by this specific model"""
    config = resolve_data_config({}, model=model)
    transform = create_transform(**config, is_training=False)
    return transform

def predict_single_image(model, transform, image_path):
    """
    Predict image class for single image using loaded model, transform, and full image path
    
    Args: 
        model: loaded model
        transform: loaded transform
        image_path: full image path

    Returns:
        image label

    Examples:
        predict_single_image(MODEL, transform, "./image_1.png")
    """
    try:
        # Open image and convert to RGB (handles PNGs with alpha channels, grayscale, etc.)
        img = Image.open(image_path).convert('RGB')
        
        # Apply transforms and add batch dimension (C, H, W) -> (1, C, H, W)
        img_tensor = transform(img).unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            outputs = model(img_tensor)
            
            # Calculate probabilities using Softmax
            probs = F.softmax(outputs, dim=1)
            
            # Get the top prediction
            confidence, preds = torch.max(probs, 1)
            
            class_idx = preds.item()
            class_name = CLASS_NAMES[class_idx]
            conf_score = confidence.item() * 100

            return class_name, conf_score

    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None, None

def predict_image(image_name, MODEL, infer_path, output_dir):
    """
    Predict image class using image path, image name, loaded model and output to the output directory
    
    Args: 
        image_name: name of the image
        MODEL: loaded Model
        infer_path: directory path containing image
        output_dir: directory path that saves the classified image

    Returns:
        image saved at output directory

    Examples:
        predict_image("./image_folder", "image_1", Model, "./result")
    """
    # Setup
    TEST_PATH = os.path.join(infer_path, image_name)
    transform = get_transform(MODEL)

    if os.path.isfile(TEST_PATH):
        # Predict one image
        label, conf = predict_single_image(MODEL, transform, TEST_PATH)
        Path(os.path.join(output_dir, 'NONSEM')).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(output_dir, 'SEM')).mkdir(parents=True, exist_ok=True)
        nonsem_destination_path = os.path.join(output_dir, 'NONSEM', image_name)
        sem_destination_path = os.path.join(output_dir, 'SEM', image_name)
        if label == 'NONSEM' and conf >= 80:
            shutil.copy2(TEST_PATH, nonsem_destination_path)
    
        if label == 'SEM' and conf >= 80:
            shutil.copy2(TEST_PATH, sem_destination_path)

def classfication_sem(data_dir, output_dir):
    """
    Predict image class using image data directory and output to the output directory
    
    Args: 
        data_dir: directory path containing image
        output_dir: directory path that saves the classified image

    Returns:
        image saved at output directory in subfolder SEM and NONSEM

    Examples:
        classfication_sem("./image_folder", "./result")
    """
    image_files = [f for f in listdir(data_dir) if isfile(join(data_dir, f))]
    MODEL = load_model()
    for i in range(len(image_files)):
        predict_image(image_files[i], MODEL, data_dir, output_dir)
