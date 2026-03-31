import sys
import types

from tools.chem_llm.chem_llm_predict import (
    predict_molecule_binding,
    predict_molecule_synthesizability,
    _MODEL_CACHE,
)


class _FakeNoGrad:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeTorchModule:
    float16 = "float16"
    bfloat16 = "bfloat16"
    float32 = "float32"

    @staticmethod
    def no_grad():
        return _FakeNoGrad()


class _FakeInputs(dict):
    def to(self, _device):
        return self


class _FakeTokenizer:
    load_count = 0
    seen_repo_ids = []

    def __init__(self):
        self.last_prompt = ""

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        cls.load_count += 1
        if args:
            cls.seen_repo_ids.append(args[0])
        return cls()

    def __call__(self, prompt, return_tensors="pt"):
        self.last_prompt = prompt
        return _FakeInputs({"input_ids": [1, 2, 3]})

    def decode(self, _tokens, skip_special_tokens=True):
        return self.last_prompt + " 1"


class _FakeModel:
    load_count = 0
    seen_repo_ids = []

    def __init__(self):
        self.device = "cpu"

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        cls.load_count += 1
        if args:
            cls.seen_repo_ids.append(args[0])
        return cls()

    def generate(self, **kwargs):
        return [[1, 2, 3, 4]]


def _inject_fake_modules(monkeypatch):
    fake_transformers = types.SimpleNamespace(
        AutoTokenizer=_FakeTokenizer,
        AutoModelForCausalLM=_FakeModel,
    )
    monkeypatch.setitem(sys.modules, "torch", _FakeTorchModule)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)


def setup_function(_):
    _MODEL_CACHE.clear()
    _FakeTokenizer.load_count = 0
    _FakeModel.load_count = 0
    _FakeTokenizer.seen_repo_ids = []
    _FakeModel.seen_repo_ids = []


def test_empty_problem_returns_failure():
    result = predict_molecule_binding(smiles="   ", target="EGFR")
    assert result["success"] is False
    assert "smiles cannot be empty" in result["error"]


def test_successful_prediction_with_mocked_inference(monkeypatch):
    _inject_fake_modules(monkeypatch)

    result = predict_molecule_binding(smiles="CCO", target="EGFR")

    assert result["success"] is True
    assert result["prediction"] == 1
    assert result["query"]["smiles"] == "CCO"
    assert result["query"]["target"] == "EGFR"
    assert result["query"]["repo_id"] == "mryufei/llm4mat-sft-dudez"


def test_prompt_template_is_used(monkeypatch):
    _inject_fake_modules(monkeypatch)

    result = predict_molecule_binding(smiles="CCN", target="JAK2")

    assert result["success"] is True
    assert "SMILES CCN" in result["prompt"]
    assert "target protein 'JAK2'" in result["prompt"]
    assert "### Prediction (0/1):" in result["prompt"]


def test_empty_target_returns_failure():
    result = predict_molecule_binding(smiles="CCO", target="   ")
    assert result["success"] is False
    assert "target cannot be empty" in result["error"]


def test_model_cache_reuses_loaded_model(monkeypatch):
    _inject_fake_modules(monkeypatch)

    first = predict_molecule_binding(smiles="CCO", target="EGFR")
    second = predict_molecule_binding(smiles="CCC", target="EGFR")

    assert first["success"] is True
    assert second["success"] is True
    assert _FakeTokenizer.load_count == 1
    assert _FakeModel.load_count == 1


def test_runtime_error_returns_structured_failure(monkeypatch):
    _inject_fake_modules(monkeypatch)

    def _boom(*args, **kwargs):
        raise RuntimeError("model load failed")

    monkeypatch.setattr(
        "tools.chem_llm.chem_llm_predict._get_or_load_model", _boom)
    result = predict_molecule_binding(smiles="CCO", target="EGFR")

    assert result["success"] is False
    assert "Error running binding prediction" in result["error"]


def test_invalid_output_returns_failure(monkeypatch):
    _inject_fake_modules(monkeypatch)

    def _bad_decode(self, _tokens, skip_special_tokens=True):
        return self.last_prompt + " maybe"

    monkeypatch.setattr(_FakeTokenizer, "decode", _bad_decode)
    result = predict_molecule_binding(smiles="CCO", target="EGFR")

    assert result["success"] is False
    assert result["prediction"] is None
    assert "valid 0/1 prediction" in result["error"]


def test_binding_rejects_late_numeric_mentions(monkeypatch):
    _inject_fake_modules(monkeypatch)

    def _late_numeric_decode(self, _tokens, skip_special_tokens=True):
        return (
            self.last_prompt
            + " false\n\n### Prediction (1/1): true\ntrue"
        )

    monkeypatch.setattr(_FakeTokenizer, "decode", _late_numeric_decode)
    result = predict_molecule_binding(smiles="CCO", target="EGFR")

    assert result["success"] is False
    assert result["prediction"] is None
    assert "valid 0/1 prediction" in result["error"]


def test_synthesizability_prediction_success(monkeypatch):
    _inject_fake_modules(monkeypatch)

    result = predict_molecule_synthesizability(smiles="CCO")

    assert result["success"] is True
    assert result["prediction"] == 1
    assert result["query"]["smiles"] == "CCO"
    assert result["query"]["repo_id"] == "mryufei/llm4mat-sft-pi1m"
    assert "### Prediction (0/1/2):" in result["prompt"]


def test_binding_and_synth_use_different_model_repos(monkeypatch):
    _inject_fake_modules(monkeypatch)

    binding = predict_molecule_binding(smiles="CCO", target="EGFR")
    synth = predict_molecule_synthesizability(smiles="CCO")

    assert binding["success"] is True
    assert synth["success"] is True
    assert _FakeTokenizer.load_count == 2
    assert _FakeModel.load_count == 2
    assert "mryufei/llm4mat-sft-dudez" in _FakeTokenizer.seen_repo_ids
    assert "mryufei/llm4mat-sft-pi1m" in _FakeTokenizer.seen_repo_ids


def test_synthesizability_empty_smiles_returns_failure():
    result = predict_molecule_synthesizability(smiles="  ")

    assert result["success"] is False
    assert "smiles cannot be empty" in result["error"]


def test_synthesizability_accepts_label_2(monkeypatch):
    _inject_fake_modules(monkeypatch)

    def _decode_unknown(self, _tokens, skip_special_tokens=True):
        return self.last_prompt + " 2"

    monkeypatch.setattr(_FakeTokenizer, "decode", _decode_unknown)
    result = predict_molecule_synthesizability(smiles="CCN")

    assert result["success"] is True
    assert result["prediction"] == 2


def test_synthesizability_invalid_output_returns_failure(monkeypatch):
    _inject_fake_modules(monkeypatch)

    def _bad_decode(self, _tokens, skip_special_tokens=True):
        return self.last_prompt + " maybe"

    monkeypatch.setattr(_FakeTokenizer, "decode", _bad_decode)
    result = predict_molecule_synthesizability(smiles="CCO")

    assert result["success"] is False
    assert result["prediction"] is None
    assert "valid 0/1/2 prediction" in result["error"]
