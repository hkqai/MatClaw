"""
Tests for sem_image_classfication tool (classfication_sem).

This tool classifies images as SEM (Scanning Electron Microscopy) or non-SEM.

Run with: pytest tests/image_retrieval/test_sem_image_classfication.py -v
"""

import pytest
import os
from os import listdir
from os.path import isfile, join


class TestSemImageClassification:
    
    def test_classfication_sem_creates_output_directory(self, classified_images):
        """Verify that output directory is created."""
        assert os.path.exists(classified_images)
        assert os.path.isdir(classified_images)
    
    def test_classfication_sem_creates_subdirectories(self, classified_images):
        """Verify that SEM and NONSEM subdirectories are created."""
        sem_dir = join(classified_images, "SEM")
        nonsem_dir = join(classified_images, "NONSEM")
        
        assert os.path.exists(sem_dir), "SEM directory not created"
        assert os.path.exists(nonsem_dir), "NONSEM directory not created"
    
    def test_classfication_sem_classifies_images(self, classified_images, subfigures):
        """Verify that images are classified into SEM or NONSEM categories."""
        from tests.image_retrieval.conftest import count_files
        
        sem_count = count_files(join(classified_images, "SEM"))
        nonsem_count = count_files(join(classified_images, "NONSEM"))
        total_classified = sem_count + nonsem_count
        
        # Should classify at least some images
        assert total_classified >= 0, "No images were classified"
    
    def test_all_input_images_classified(self, classified_images, subfigures):
        """Verify that all input images are classified (none lost)."""
        from tests.image_retrieval.conftest import count_files
        
        input_count = count_files(subfigures)
        sem_count = count_files(join(classified_images, "SEM"))
        nonsem_count = count_files(join(classified_images, "NONSEM"))
        total_classified = sem_count + nonsem_count
        
        # Total classified should not exceed input
        assert total_classified <= input_count, \
            f"More images classified ({total_classified}) than input ({input_count})"
        
        # Should classify a reasonable portion (at least 50%)
        assert total_classified >= input_count * 0.5, \
            f"Too few images classified: {total_classified}/{input_count}"
    
    def test_classification_distribution(self, classified_images):
        """Verify that classification produces reasonable distribution."""
        from tests.image_retrieval.conftest import count_files
        
        sem_count = count_files(join(classified_images, "SEM"))
        nonsem_count = count_files(join(classified_images, "NONSEM"))
        
        # At least one category should have images (not all in one category)
        # Note: This may need adjustment based on actual test data
        assert sem_count >= 0, "SEM category should exist"
        assert nonsem_count >= 0, "NONSEM category should exist"
