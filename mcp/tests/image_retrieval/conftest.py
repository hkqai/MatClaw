"""
Shared fixtures for image_retrieval tests.

These fixtures handle the sequential data generation and cleanup for the
image retrieval test suite.
"""

import pytest
import os
import shutil
from os import listdir
from os.path import isfile, join


@pytest.fixture(scope="session")
def test_dirs():
    """
    Provide test directory paths.
    
    Returns a dict with paths for pdf input and all output directories.
    """
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    return {
        "test_dir": test_dir,
        "pdf_path": os.path.join(test_dir, "pdf_folder"),
        "pdf_image_output": os.path.join(test_dir, "pdf_image"),
        "subfigures_output": os.path.join(test_dir, "subfigures"),
        "classification_output": os.path.join(test_dir, "classification")
    }


@pytest.fixture(scope="session")
def pdf_images(test_dirs):
    """
    Extract figures from PDFs once for all tests.
    
    Returns the path to the pdf_image directory.
    Cleans up the directory first if it exists.
    """
    from tools.image_retrieval.paper_image_extract import get_paper_figure
    
    pdf_path = test_dirs["pdf_path"]
    output_path = test_dirs["pdf_image_output"]
    
    # Clean up if exists
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    
    # Extract figures
    get_paper_figure(pdf_path, output_path)
    
    yield output_path
    
    # Cleanup after all tests
    if os.path.exists(output_path):
        shutil.rmtree(output_path)


@pytest.fixture(scope="session")
def subfigures(test_dirs, pdf_images):
    """
    Extract subfigures from PDF images once for all tests.
    
    Depends on pdf_images fixture. Returns path to subfigures directory.
    """
    from tools.image_retrieval.image_segmentation import extract_all_subfigures
    
    output_path = test_dirs["subfigures_output"]
    
    # Clean up if exists
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    
    # Extract subfigures
    extract_all_subfigures(pdf_images, output_path)
    
    yield output_path
    
    # Cleanup after all tests
    if os.path.exists(output_path):
        shutil.rmtree(output_path)


@pytest.fixture(scope="session")
def classified_images(test_dirs, subfigures):
    """
    Classify SEM images once for all tests.
    
    Depends on subfigures fixture. Returns path to classification directory.
    """
    from tools.image_retrieval.sem_image_classfication import classfication_sem
    
    output_path = test_dirs["classification_output"]
    
    # Clean up if exists
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    
    # Classify images
    classfication_sem(subfigures, output_path)
    
    yield output_path
    
    # Cleanup after all tests
    if os.path.exists(output_path):
        shutil.rmtree(output_path)


def count_files(directory):
    """Helper function to count files in a directory."""
    if not os.path.exists(directory):
        return 0
    return len([f for f in listdir(directory) if isfile(join(directory, f))])
