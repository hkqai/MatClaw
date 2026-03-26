"""
Tests for multi_objective_ranker tool.

Run with: pytest tests/selection/test_multi_objective_ranker.py -v
"""

import pytest
from tools.selection.multi_objective_ranker import multi_objective_ranker


class TestMultiObjectiveRanker:
    """Tests for multi-objective ranking."""

    @pytest.fixture
    def simple_candidates(self):
        """Simple test dataset with 2 objectives."""
        return [
            {"id": "mat_001", "objectives": {"stability": -2.5, "synthesizability": 0.9}},
            {"id": "mat_002", "objectives": {"stability": -1.8, "synthesizability": 0.7}},
            {"id": "mat_003", "objectives": {"stability": -3.2, "synthesizability": 0.5}},
            {"id": "mat_004", "objectives": {"stability": -1.5, "synthesizability": 0.95}},
            {"id": "mat_005", "objectives": {"stability": -2.0, "synthesizability": 0.85}},
        ]

    @pytest.fixture
    def three_objective_candidates(self):
        """Dataset with 3 objectives for more complex testing."""
        return [
            {"id": "A", "objectives": {"energy": -5.0, "gap": 2.5, "volume": 100}},
            {"id": "B", "objectives": {"energy": -4.5, "gap": 3.0, "volume": 95}},
            {"id": "C", "objectives": {"energy": -5.5, "gap": 2.0, "volume": 105}},
            {"id": "D", "objectives": {"energy": -4.0, "gap": 3.5, "volume": 90}},
            {"id": "E", "objectives": {"energy": -6.0, "gap": 1.5, "volume": 110}},
        ]

    def test_pareto_ranking_basic(self, simple_candidates):
        """Test basic Pareto frontier ranking."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="pareto",
            top_k=5
        )
        
        assert result["success"] is True
        assert result["strategy"] == "pareto"
        assert result["total_candidates"] == 5
        assert len(result["ranked_candidates"]) <= 5
        assert "pareto_fronts" in result
        assert result["num_fronts"] >= 1
        
        # Check that all candidates have required fields
        for candidate in result["ranked_candidates"]:
            assert "rank" in candidate
            assert "score" in candidate
            assert "pareto_front" in candidate
            assert "dominated_count" in candidate

    def test_pareto_dominance(self):
        """Test that Pareto dominance works correctly."""
        candidates = [
            {"id": "dominated", "objectives": {"a": 5.0, "b": 5.0}},
            {"id": "dominates", "objectives": {"a": 3.0, "b": 7.0}},
        ]
        objectives = {"a": "minimize", "b": "maximize"}
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives=objectives,
            strategy="pareto"
        )
        
        assert result["success"] is True
        # The dominating candidate should be rank 1
        ranked = {c["id"]: c for c in result["ranked_candidates"]}
        assert ranked["dominates"]["rank"] == 1
        assert ranked["dominates"]["pareto_front"] == 1
        assert ranked["dominated"]["pareto_front"] == 2

    def test_weighted_sum_ranking(self, simple_candidates):
        """Test weighted sum ranking strategy."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        weights = {"stability": 0.6, "synthesizability": 0.4}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="weighted_sum",
            weights=weights,
            top_k=3
        )
        
        assert result["success"] is True
        assert result["strategy"] == "weighted_sum"
        assert len(result["ranked_candidates"]) == 3
        assert "weights_used" in result
        assert result["weights_used"] == weights
        
        # Check ranks are sequential
        ranks = [c["rank"] for c in result["ranked_candidates"]]
        assert ranks == [1, 2, 3]
        
        # Scores should be in descending order
        scores = [c["score"] for c in result["ranked_candidates"]]
        assert scores == sorted(scores, reverse=True)

    def test_weighted_sum_requires_weights(self, simple_candidates):
        """Test that weighted_sum strategy requires weights parameter."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="weighted_sum"
        )
        
        assert result["success"] is False
        assert "weights" in result["error"].lower()

    def test_weights_must_sum_to_one(self, simple_candidates):
        """Test that weights must sum to 1.0."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        weights = {"stability": 0.7, "synthesizability": 0.5}  # Sum = 1.2
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="weighted_sum",
            weights=weights
        )
        
        assert result["success"] is False
        assert "sum to 1.0" in result["error"]

    def test_constraint_ranking(self, simple_candidates):
        """Test constraint-based ranking strategy."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        constraints = {"synthesizability": {"min": 0.8}}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="constraint",
            constraints=constraints,
            primary_objective="stability",
            top_k=5
        )
        
        assert result["success"] is True
        assert result["strategy"] == "constraint"
        assert result["feasible_count"] >= 1
        assert result["primary_objective"] == "stability"
        
        # All ranked candidates should satisfy constraints (check original values)
        for candidate in result["ranked_candidates"]:
            obj_dict = candidate.get("original_objectives", candidate["objectives"])
            assert obj_dict["synthesizability"] >= 0.8

    def test_constraint_no_feasible(self):
        """Test constraint strategy when no candidates satisfy constraints."""
        candidates = [
            {"id": "mat_001", "objectives": {"stability": -2.5, "synthesizability": 0.3}},
            {"id": "mat_002", "objectives": {"stability": -1.8, "synthesizability": 0.4}},
        ]
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        constraints = {"synthesizability": {"min": 0.9}}
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives=objectives,
            strategy="constraint",
            constraints=constraints,
            primary_objective="stability"
        )
        
        assert result["success"] is False
        assert result["feasible_count"] == 0
        assert "no candidates satisfy" in result["error"].lower()

    def test_constraint_requires_primary_objective(self, simple_candidates):
        """Test that constraint strategy requires primary_objective."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="constraint"
        )
        
        assert result["success"] is False
        assert "primary_objective" in result["error"]

    def test_top_k_limiting(self, simple_candidates):
        """Test that top_k limits results correctly."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="pareto",
            top_k=2
        )
        
        assert result["success"] is True
        assert len(result["ranked_candidates"]) <= 2

    def test_three_objectives(self, three_objective_candidates):
        """Test ranking with three objectives."""
        objectives = {
            "energy": "minimize",
            "gap": "maximize",
            "volume": "minimize"
        }
        
        result = multi_objective_ranker(
            candidates=three_objective_candidates,
            objectives=objectives,
            strategy="pareto"
        )
        
        assert result["success"] is True
        assert len(result["ranked_candidates"]) == 5

    def test_normalization_disabled(self, simple_candidates):
        """Test with normalization disabled."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        weights = {"stability": 0.5, "synthesizability": 0.5}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="weighted_sum",
            weights=weights,
            normalize_objectives=False
        )
        
        assert result["success"] is True
        assert result["normalize_objectives"] is False
        assert "objective_ranges" not in result

    def test_normalization_enabled(self, simple_candidates):
        """Test with normalization enabled."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        weights = {"stability": 0.5, "synthesizability": 0.5}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="weighted_sum",
            weights=weights,
            normalize_objectives=True
        )
        
        assert result["success"] is True
        assert result["normalize_objectives"] is True
        assert "objective_ranges" in result
        assert "stability" in result["objective_ranges"]
        assert "synthesizability" in result["objective_ranges"]

    def test_statistics_computation(self, simple_candidates):
        """Test that statistics are computed correctly."""
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="pareto"
        )
        
        assert result["success"] is True
        assert "statistics" in result
        stats = result["statistics"]
        assert "count" in stats
        assert "objective_stats" in stats
        assert "stability" in stats["objective_stats"]
        assert "synthesizability" in stats["objective_stats"]
        
        # Check that stats contain expected keys
        for obj_name in objectives.keys():
            obj_stats = stats["objective_stats"][obj_name]
            assert "min" in obj_stats
            assert "max" in obj_stats
            assert "mean" in obj_stats
            assert "median" in obj_stats

    def test_empty_candidates_list(self):
        """Test error handling for empty candidates list."""
        result = multi_objective_ranker(
            candidates=[],
            objectives={"stability": "minimize"},
            strategy="pareto"
        )
        
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_missing_candidate_id(self):
        """Test error handling for candidate missing id."""
        candidates = [{"objectives": {"stability": -2.5}}]
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives={"stability": "minimize"},
            strategy="pareto"
        )
        
        assert result["success"] is False
        assert "missing required 'id'" in result["error"].lower()

    def test_missing_candidate_objectives(self):
        """Test error handling for candidate missing objectives."""
        candidates = [{"id": "mat_001"}]
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives={"stability": "minimize"},
            strategy="pareto"
        )
        
        assert result["success"] is False
        assert "missing 'objectives'" in result["error"].lower()

    def test_invalid_objective_direction(self, simple_candidates):
        """Test error handling for invalid objective direction."""
        objectives = {"stability": "reduce"}  # Invalid direction
        
        result = multi_objective_ranker(
            candidates=simple_candidates,
            objectives=objectives,
            strategy="pareto"
        )
        
        assert result["success"] is False
        assert "minimize" in result["error"] or "maximize" in result["error"]

    def test_candidate_missing_objective_value(self):
        """Test error handling when candidate missing an objective value."""
        candidates = [
            {"id": "mat_001", "objectives": {"stability": -2.5}},
        ]
        objectives = {"stability": "minimize", "synthesizability": "maximize"}
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives=objectives,
            strategy="pareto"
        )
        
        assert result["success"] is False
        assert "missing objective" in result["error"].lower()

    def test_nan_objective_value(self):
        """Test error handling for NaN objective values."""
        import math
        candidates = [
            {"id": "mat_001", "objectives": {"stability": math.nan}},
        ]
        objectives = {"stability": "minimize"}
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives=objectives,
            strategy="pareto"
        )
        
        assert result["success"] is False
        assert "invalid value" in result["error"].lower()

    def test_diverse_objectives(self):
        """Test with objectives of different scales."""
        candidates = [
            {"id": "A", "objectives": {"energy": -1000.5, "gap": 2.5, "synth": 0.8}},
            {"id": "B", "objectives": {"energy": -999.2, "gap": 3.0, "synth": 0.9}},
            {"id": "C", "objectives": {"energy": -1001.0, "gap": 2.0, "synth": 0.7}},
        ]
        objectives = {
            "energy": "minimize",
            "gap": "maximize",
            "synth": "maximize"
        }
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives=objectives,
            strategy="pareto",
            normalize_objectives=True
        )
        
        assert result["success"] is True
        # With normalization, should handle different scales properly
        assert "objective_ranges" in result


class TestDiversityFiltering:
    """Tests for diversity filtering functionality."""

    def test_diversity_filter_without_structure(self):
        """Test that diversity filter fails gracefully without structures."""
        candidates = [
            {"id": "mat_001", "objectives": {"stability": -2.5}},
            {"id": "mat_002", "objectives": {"stability": -1.8}},
        ]
        objectives = {"stability": "minimize"}
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives=objectives,
            strategy="pareto",
            diversity_filter=True
        )
        
        # Should succeed but warn about diversity filter
        assert result["success"] is True
        assert result.get("diversity_filtered") is False
        assert "diversity_filter_error" in result

    def test_diversity_filter_with_structures(self):
        """Test diversity filtering with structure data."""
        candidates = [
            {
                "id": "mat_001",
                "objectives": {"stability": -2.5},
                "structure": {"@class": "Structure", "data": "..."}
            },
            {
                "id": "mat_002",
                "objectives": {"stability": -1.8},
                "structure": {"@class": "Structure", "data": "..."}
            },
        ]
        objectives = {"stability": "minimize"}
        
        result = multi_objective_ranker(
            candidates=candidates,
            objectives=objectives,
            strategy="pareto",
            diversity_filter=True,
            diversity_threshold=0.1
        )
        
        assert result["success"] is True
        # With placeholder similarity function, all should be selected
        assert result.get("diversity_filtered") is True
        assert result.get("diversity_threshold") == 0.1
