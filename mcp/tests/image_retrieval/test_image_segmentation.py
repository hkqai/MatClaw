"""
Tests for image_segmentation tool (extract_all_subfigures).

This tool segments images into subfigures/panels.

Run with: pytest tests/image_retrieval/test_image_segmentation.py -v
"""

import pytest
from os import listdir
from os.path import isfile, join


class TestImageSegmentation:
    
    def test_extract_all_subfigures_creates_output_directory(self, subfigures):
        """Verify that output directory is created."""
        import os
        assert os.path.exists(subfigures)
        assert os.path.isdir(subfigures)
    
    def test_extract_all_subfigures_extracts_panels(self, subfigures):
        """Verify that at least one subfigure panel is extracted."""
        from tests.image_retrieval.conftest import count_files
        panel_count = count_files(subfigures)
        assert panel_count >= 1, f"Expected at least 1 panel, found {panel_count}"
    
    def test_extracted_panels_are_files(self, subfigures):
        """Verify that extracted panels are actual image files."""
        files = [f for f in listdir(subfigures) if isfile(join(subfigures, f))]
        assert len(files) >= 1, "No panel files found in output directory"
        
        # Check naming pattern (should contain "panel")
        panel_files = [f for f in files if "panel" in f.lower()]
        assert len(panel_files) >= 1, "No files with 'panel' in name found"
    
    def test_panel_count_reasonable(self, pdf_images, subfigures):
        """Verify that number of panels is reasonable compared to input images."""
        from tests.image_retrieval.conftest import count_files
        input_count = count_files(pdf_images)
        output_count = count_files(subfigures)
        
        # Each input image should produce at least 1 panel (could be many more)
        assert output_count >= input_count, \
            f"Expected at least {input_count} panels, got {output_count}"
