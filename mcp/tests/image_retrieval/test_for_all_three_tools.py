"""
Tests for tools in image_retrieval.

These tests uses sample_pdf store in the test folder and test get_paper_figure first, then extract_all_subfigures, and classfication_sem

Run with: pytest tests/image_retrieval/test_for_all_three_tools.py -v
"""

import pytest

from tools.image_retrieval.sem_image_classfication import classfication_sem
from tools.image_retrieval.image_segmentation import extract_all_subfigures
from tools.image_retrieval.paper_image_extract import get_paper_figure


#from .sem_image_classfication import classfication_sem
#from .image_segmentation import extract_all_subfigures
#from .paper_image_extract import get_paper_figure
from os import listdir
from os.path import isfile, join


pdf_path = "./pdf_folder"
pdf_image_output_path = "./pdf_image"
pdf_image_sub_figure_path = "./subfigures"
sem_image_folder = "./classification"


class TestImageSegmentation:
    def test_get_paper_figure(self):
        """Extract figures from sample pdf, assert output image file in the directory is larger than 1"""
        get_paper_figure(pdf_path, pdf_image_output_path)
        image_files = [f for f in listdir(pdf_image_output_path) if isfile(join(pdf_image_output_path, f))]
        assert len(image_files) >= 1

    def test_extract_all_subfigures(self):
        """Extract all subfigures from the paper figure, assert output image file in the directory is larger than 1"""
        extract_all_subfigures(pdf_image_output_path, pdf_image_sub_figure_path)
        image_files = [f for f in listdir(pdf_image_sub_figure_path) if isfile(join(pdf_image_sub_figure_path, f))]
        assert len(image_files) >= 1

    def test_classfication_sem(self):
        """Classify SEM image and save in the sem_image_folder, assert output image file in the directory is larger than 1"""
        classfication_sem(pdf_image_sub_figure_path, sem_image_folder)
        image_files = [f for f in listdir(pdf_image_sub_figure_path) if isfile(join(pdf_image_sub_figure_path, f))]
        sem_image_files = [f for f in listdir(join(sem_image_folder, "SEM")) if isfile(join(sem_image_folder, "SEM", f))]
        non_sem_image_files = [f for f in listdir(join(sem_image_folder, "NONSEM")) if isfile(join(sem_image_folder, "NONSEM", f))]
        assert (len(sem_image_files) + len(non_sem_image_files) >= 0 and len(sem_image_files) + len(non_sem_image_files) <= len(image_files))