"""
Tests for paper_image_extract tool (get_paper_figure).

This tool extracts figures from PDF files containing scientific papers.

Run with: pytest tests/image_retrieval/test_paper_image_extract.py -v
"""

import pytest
from os import listdir
from os.path import isfile, join


class TestPaperImageExtract:
    
    def test_get_paper_figure_creates_output_directory(self, pdf_images):
        """Verify that output directory is created."""
        import os
        assert os.path.exists(pdf_images)
        assert os.path.isdir(pdf_images)
    
    def test_get_paper_figure_extracts_images(self, pdf_images):
        """Verify that at least one image is extracted from PDF."""
        from tests.image_retrieval.conftest import count_files
        image_count = count_files(pdf_images)
        assert image_count >= 1, f"Expected at least 1 image, found {image_count}"
    
    def test_extracted_images_are_files(self, pdf_images):
        """Verify that extracted items are actual files."""
        files = [f for f in listdir(pdf_images) if isfile(join(pdf_images, f))]
        assert len(files) >= 1, "No files found in output directory"
        
        # Check first file has reasonable size (>1KB)
        import os
        first_file = join(pdf_images, files[0])
        file_size = os.path.getsize(first_file)
        assert file_size > 1024, f"File {files[0]} seems too small ({file_size} bytes)"
