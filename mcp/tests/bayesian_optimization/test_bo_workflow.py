"""
Tests for Bayesian Optimization tools.

These tests validate the complete BO workflow:
1. Campaign initialization
2. Observation recording
3. Experiment suggestion
"""

import pytest
import os
import shutil
import tempfile
from pathlib import Path


@pytest.fixture
def temp_campaign_dir():
    """Create a temporary directory for campaign files."""
    temp_dir = tempfile.mkdtemp(prefix="bo_test_")
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def sample_parameter_space():
    """Sample parameter space for testing."""
    return [
        {
            "name": "temperature",
            "type": "continuous",
            "bounds": [400, 1200],
            "unit": "C"
        },
        {
            "name": "pressure",
            "type": "continuous",
            "bounds": [0.1, 10],
            "unit": "atm"
        },
        {
            "name": "precursor",
            "type": "categorical",
            "choices": ["Li2CO3", "LiOH", "Li2O"]
        },
        {
            "name": "stirring_speed",
            "type": "discrete",
            "values": [100, 200, 500, 1000],
            "unit": "rpm"
        }
    ]


@pytest.fixture
def sample_objective_config():
    """Sample objective configuration."""
    return {
        "type": "single_objective",
        "metrics": ["phase_purity"],
        "direction": "maximize"
    }


class TestBOInitializeCampaign:
    """Tests for bo_initialize_campaign."""

    def test_initialize_basic(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test basic campaign initialization."""
        from tools.bayesian_optimization import bo_initialize_campaign

        result = bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            n_initial_random=5
        )

        assert result["success"] is True
        assert result["n_parameters"] == 4
        assert result["n_initial_random"] == 5
        assert len(result["initial_suggestions"]) == 5
        assert os.path.exists(result["state_file"])
        assert os.path.exists(result["observations_file"])

    def test_initialize_with_metadata(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test initialization with metadata."""
        from tools.bayesian_optimization import bo_initialize_campaign

        metadata = {"project": "test", "operator": "pytest"}

        result = bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            campaign_name="Test Campaign",
            metadata=metadata
        )

        assert result["success"] is True
        assert result["campaign_name"] == "Test Campaign"

    def test_invalid_parameter_space(self, temp_campaign_dir, sample_objective_config):
        """Test handling of invalid parameter space."""
        from tools.bayesian_optimization import bo_initialize_campaign

        # Missing 'type' field
        invalid_space = [{"name": "temp"}]

        result = bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=invalid_space,
            objective_config=sample_objective_config
        )

        assert result["success"] is False
        assert "Invalid parameter_space" in result["error"]

    def test_invalid_objective_config(self, temp_campaign_dir, sample_parameter_space):
        """Test handling of invalid objective config."""
        from tools.bayesian_optimization import bo_initialize_campaign

        # Missing 'metrics' field
        invalid_config = {"type": "single_objective"}

        result = bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=invalid_config
        )

        assert result["success"] is False
        assert "Invalid objective_config" in result["error"]


class TestBORecordObservation:
    """Tests for bo_record_result."""

    def test_record_basic(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test basic observation recording."""
        from tools.bayesian_optimization import bo_initialize_campaign, bo_record_result

        # Initialize campaign
        init_result = bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            n_initial_random=3
        )
        assert init_result["success"] is True

        # Record first observation
        params = {
            "temperature": 800.0,
            "pressure": 1.0,
            "precursor": "Li2CO3",
            "stirring_speed": 500
        }
        observations = {"phase_purity": 0.85}

        result = bo_record_result(
            campaign_dir=temp_campaign_dir,
            parameters=params,
            observations=observations
        )

        assert result["success"] is True
        assert result["n_observations"] == 1
        assert result["initial_phase"] is True
        assert result["objective_value"] == 0.85

    def test_record_with_metadata(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test recording with metadata."""
        from tools.bayesian_optimization import bo_initialize_campaign, bo_record_result

        init_result = bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config
        )

        params = {
            "temperature": 850.0,
            "pressure": 1.5,
            "precursor": "LiOH",
            "stirring_speed": 200
        }
        observations = {"phase_purity": 0.92, "crystallinity": 0.88}
        metadata = {"xrd_file": "/path/to/xrd.xy", "operator": "pytest"}

        result = bo_record_result(
            campaign_dir=temp_campaign_dir,
            parameters=params,
            observations=observations,
            metadata=metadata,
            observation_id="test_001"
        )

        assert result["success"] is True
        assert result["observation_id"] == "test_001"

    def test_missing_parameters(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test handling of missing parameters."""
        from tools.bayesian_optimization import bo_initialize_campaign, bo_record_result

        bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config
        )

        # Missing 'temperature' parameter
        params = {"pressure": 1.0, "precursor": "Li2O", "stirring_speed": 100}
        observations = {"phase_purity": 0.75}

        result = bo_record_result(
            campaign_dir=temp_campaign_dir,
            parameters=params,
            observations=observations
        )

        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    def test_missing_objective_metric(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test handling of missing objective metric."""
        from tools.bayesian_optimization import bo_initialize_campaign, bo_record_result

        bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config
        )

        params = {
            "temperature": 900.0,
            "pressure": 2.0,
            "precursor": "Li2CO3",
            "stirring_speed": 1000
        }
        # Missing 'phase_purity' objective
        observations = {"crystallinity": 0.90}

        result = bo_record_result(
            campaign_dir=temp_campaign_dir,
            parameters=params,
            observations=observations
        )

        assert result["success"] is False
        assert "Missing required objective metrics" in result["error"]


class TestBOSuggestExperiment:
    """Tests for bo_suggest_experiment."""

    def test_suggest_random_initial_phase(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test suggestions during initial random phase."""
        from tools.bayesian_optimization import bo_initialize_campaign, bo_suggest_experiment

        bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            n_initial_random=5
        )

        result = bo_suggest_experiment(
            campaign_dir=temp_campaign_dir,
            batch_size=1
        )

        assert result["success"] is True
        assert result["using_gp_model"] is False
        assert result["n_suggestions"] == 1
        assert len(result["suggestions"]) == 1

    def test_suggest_with_gp_model(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test suggestions using GP model after initial phase."""
        from tools.bayesian_optimization import (
            bo_initialize_campaign,
            bo_record_result,
            bo_suggest_experiment
        )

        # Initialize
        bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            n_initial_random=3
        )

        # Record enough observations to complete initial phase
        test_data = [
            ({"temperature": 600, "pressure": 1.0, "precursor": "Li2CO3", "stirring_speed": 100}, 0.70),
            ({"temperature": 800, "pressure": 2.0, "precursor": "LiOH", "stirring_speed": 500}, 0.85),
            ({"temperature": 1000, "pressure": 5.0, "precursor": "Li2O", "stirring_speed": 1000}, 0.92),
        ]

        for params, purity in test_data:
            bo_record_result(
                campaign_dir=temp_campaign_dir,
                parameters=params,
                observations={"phase_purity": purity}
            )

        # Now suggest should use GP model
        result = bo_suggest_experiment(
            campaign_dir=temp_campaign_dir,
            batch_size=2,
            acquisition_function="ei"
        )

        assert result["success"] is True
        assert result["using_gp_model"] is True
        assert result["n_suggestions"] == 2
        assert "gp_model_score" in result
        assert "best_observed_value" in result

    def test_batch_suggestions(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test batch suggestion generation."""
        from tools.bayesian_optimization import (
            bo_initialize_campaign,
            bo_record_result,
            bo_suggest_experiment
        )

        bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            n_initial_random=2
        )

        # Add observations
        for i in range(3):
            params = {
                "temperature": 600 + i * 200,
                "pressure": 1.0 + i,
                "precursor": ["Li2CO3", "LiOH", "Li2O"][i],
                "stirring_speed": [100, 500, 1000][i]
            }
            bo_record_result(
                campaign_dir=temp_campaign_dir,
                parameters=params,
                observations={"phase_purity": 0.7 + i * 0.1}
            )

        result = bo_suggest_experiment(
            campaign_dir=temp_campaign_dir,
            batch_size=3,
            acquisition_function="ucb",
            exploration_weight=2.0
        )

        assert result["success"] is True
        assert result["n_suggestions"] == 3

    def test_different_acquisition_functions(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test different acquisition functions."""
        from tools.bayesian_optimization import (
            bo_initialize_campaign,
            bo_record_result,
            bo_suggest_experiment
        )

        bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            n_initial_random=2
        )

        # Add observations
        for i in range(3):
            params = {
                "temperature": 700 + i * 100,
                "pressure": 1.0,
                "precursor": "Li2CO3",
                "stirring_speed": 500
            }
            bo_record_result(
                campaign_dir=temp_campaign_dir,
                parameters=params,
                observations={"phase_purity": 0.75 + i * 0.05}
            )

        for acq_func in ["ei", "ucb", "pi", "random"]:
            result = bo_suggest_experiment(
                campaign_dir=temp_campaign_dir,
                acquisition_function=acq_func
            )
            assert result["success"] is True
            assert result["acquisition_function"] == acq_func


class TestBOEndToEnd:
    """End-to-end tests for complete BO workflow."""

    def test_complete_workflow(self, temp_campaign_dir, sample_parameter_space, sample_objective_config):
        """Test complete BO workflow from initialization to optimization."""
        from tools.bayesian_optimization import (
            bo_initialize_campaign,
            bo_record_result,
            bo_suggest_experiment
        )

        # 1. Initialize campaign
        init_result = bo_initialize_campaign(
            campaign_dir=temp_campaign_dir,
            parameter_space=sample_parameter_space,
            objective_config=sample_objective_config,
            n_initial_random=3,
            campaign_name="End-to-End Test",
            random_seed=42
        )
        assert init_result["success"] is True

        # 2. Run initial random experiments
        for i in range(3):
            suggest_result = bo_suggest_experiment(
                campaign_dir=temp_campaign_dir,
                random_seed=42 + i
            )
            assert suggest_result["success"] is True
            assert not suggest_result["using_gp_model"]

            # Simulate experiment with mock result
            params = suggest_result["suggestions"][0]
            mock_purity = 0.7 + (params["temperature"] / 1200) * 0.2

            record_result = bo_record_result(
                campaign_dir=temp_campaign_dir,
                parameters=params,
                observations={"phase_purity": mock_purity}
            )
            assert record_result["success"] is True

        # 3. Check that initial phase is complete
        last_record = record_result
        assert last_record["initial_phase_complete"] is True

        # 4. Run BO-guided experiments
        for i in range(3):
            suggest_result = bo_suggest_experiment(
                campaign_dir=temp_campaign_dir,
                acquisition_function="ei",
                random_seed=100 + i
            )
            assert suggest_result["success"] is True
            assert suggest_result["using_gp_model"] is True

            # Record observation
            params = suggest_result["suggestions"][0]
            mock_purity = 0.75 + (params["temperature"] / 1200) * 0.15

            record_result = bo_record_result(
                campaign_dir=temp_campaign_dir,
                parameters=params,
                observations={"phase_purity": mock_purity}
            )
            assert record_result["success"] is True

        # 5. Verify optimization improved
        final_suggest = bo_suggest_experiment(campaign_dir=temp_campaign_dir)
        assert final_suggest["success"] is True
        assert final_suggest["n_observations"] == 6
        assert "best_observed_value" in final_suggest
