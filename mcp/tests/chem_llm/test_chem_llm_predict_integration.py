import os

import pytest

from tools.chem_llm.chem_llm_predict import (
    _MODEL_CACHE,
    predict_molecule_binding,
    predict_molecule_synthesizability,
)


pytestmark = [pytest.mark.integration, pytest.mark.slow]


def setup_function(_):
    _MODEL_CACHE.clear()


def _require_real_inference_enabled() -> None:
    flag = os.getenv("RUN_REAL_LLM_INFERENCE_TESTS", "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        pytest.skip(
            "Real LLM inference tests are disabled. "
            "Set RUN_REAL_LLM_INFERENCE_TESTS=1 to enable."
        )


def _require_runtime_dependencies() -> None:
    pytest.importorskip(
        "torch", reason="torch is required for real inference tests")
    pytest.importorskip(
        "transformers", reason="transformers is required for real inference tests"
    )
    pytest.importorskip(
        "accelerate",
        reason="accelerate is required when model loading uses device_map='auto'",
    )


def _set_hf_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not hf_token:
        pytest.skip(
            "Missing Hugging Face token. Set HF_TOKEN or HUGGINGFACEHUB_API_TOKEN."
        )
    monkeypatch.setenv("HF_TOKEN", hf_token)


def _print_inference_result(test_name: str, result: dict) -> None:
    print(
        f"\n[{test_name}] success={result.get('success')} prediction={result.get('prediction')}")
    if result.get("error"):
        print(f"[{test_name}] error={result.get('error')}")
    print(f"[{test_name}] raw_output:\n{result.get('raw_output')}")


def _assert_inference_result(
    result: dict,
    allowed_labels: set[int],
) -> None:
    if not result["success"]:
        pytest.fail(
            f"Real inference failed: {result.get('error')}\n"
            f"raw_output={result.get('raw_output')}"
        )

    assert result["prediction"] in allowed_labels
    assert isinstance(result.get("raw_output"), str)
    assert result["raw_output"].strip()


def test_real_binding_inference_smoke(monkeypatch: pytest.MonkeyPatch):
    _require_real_inference_enabled()
    _require_runtime_dependencies()
    _set_hf_token_from_env(monkeypatch)

    result = predict_molecule_binding(smiles="CCO", target="EGFR")
    _print_inference_result("binding:CCO:EGFR", result)

    assert result["query"]["smiles"] == "CCO"
    assert result["query"]["target"] == "EGFR"
    assert result["query"]["repo_id"] == "mryufei/llm4mat-sft-dudez"
    _assert_inference_result(
        result=result,
        allowed_labels={0, 1},
    )


@pytest.mark.parametrize(
    "smiles",
    [
        "CCO",
        "CC(=O)Oc1ccccc1C(=O)O",
    ],
)
def test_real_synthesizability_inference_smoke(
    monkeypatch: pytest.MonkeyPatch, smiles: str
):
    _require_real_inference_enabled()
    _require_runtime_dependencies()
    _set_hf_token_from_env(monkeypatch)

    result = predict_molecule_synthesizability(smiles=smiles)
    _print_inference_result(f"synth:{smiles}", result)

    assert result["query"]["smiles"] == smiles
    assert result["query"]["repo_id"] == "mryufei/llm4mat-sft-pi1m"
    _assert_inference_result(
        result=result,
        allowed_labels={0, 1, 2},
    )
