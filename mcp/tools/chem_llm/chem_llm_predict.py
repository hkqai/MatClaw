"""Task-specific tool: predict molecule-target binding activity (0/1)."""

from typing import Dict, Any, Optional, Annotated
from pydantic import Field
import os
import re


SYNTHESIZABILITY_REPO_ID = "mryufei/llm4mat-sft-pi1m"
BINDING_REPO_ID = "mryufei/llm4mat-sft-dudez"
SUBFOLDER = "merged"
TORCH_DTYPE = "bfloat16"
DEVICE_MAP = "auto"
MAX_NEW_TOKENS = 16
TEMPERATURE = 0.1
TOP_P = 0.95

BINDING_PROMPT_TEMPLATE = (
    "### Instructions:\n"
    "Predict whether the molecule with SMILES {smiles} can bind to the target "
    "protein '{target}' (1 = active, 0 = inactive).\n\n"
    "### Prediction (0/1):"
)

SYNTHESIZABILITY_PROMPT_TEMPLATE = (
    "### Instructions:\n"
    "Predict whether the molecule with SMILES {smiles} is synthesizable "
    "(1 = yes, 0 = no, 2 = unknown).\n\n"
    "### Prediction (0/1/2):"
)

_MODEL_CACHE: dict[tuple[str, Optional[str]], tuple[Any, Any]] = {}


def _resolve_torch_dtype(torch_module: Any, dtype_name: str) -> Any:
    mapping = {
        "float16": torch_module.float16,
        "bfloat16": torch_module.bfloat16,
        "float32": torch_module.float32,
    }
    return mapping[dtype_name]


def _get_or_load_model(repo_id: str, hf_token: Optional[str]) -> tuple[Any, Any]:
    """Load fixed tokenizer/model once and reuse across calls."""
    cache_key = (repo_id, hf_token)
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    import torch  # type: ignore
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    tokenizer = AutoTokenizer.from_pretrained(
        repo_id,
        subfolder=SUBFOLDER,
        token=hf_token,
    )

    model = AutoModelForCausalLM.from_pretrained(
        repo_id,
        subfolder=SUBFOLDER,
        torch_dtype=_resolve_torch_dtype(torch, TORCH_DTYPE),
        device_map=DEVICE_MAP,
        token=hf_token,
    )

    _MODEL_CACHE[cache_key] = (tokenizer, model)
    return tokenizer, model


def _extract_prediction(text: str, allowed_labels: set[int]) -> Optional[int]:
    """Extract a leading numeric label from generated text."""
    stripped = text.strip()
    if not stripped:
        return None

    label_pattern = "|".join(str(v)
                             for v in sorted(allowed_labels, reverse=True))
    match = re.match(rf"^({label_pattern})(?!\d)", stripped)
    if match:
        return int(match.group(1))

    for label in sorted(allowed_labels):
        if stripped.startswith(str(label)):
            return label
    return None


def _run_prediction(
    smiles: str,
    prompt: str,
    repo_id: str,
    allowed_labels: set[int],
    invalid_output_error: str,
    runtime_error_prefix: str,
) -> Dict[str, Any]:
    query = {
        "smiles": smiles,
        "repo_id": repo_id,
    }
    hf_token = os.getenv("HF_TOKEN")

    try:
        import torch  # type: ignore
    except ImportError:
        return {
            "success": False,
            "query": query,
            "prediction": None,
            "error": "Missing dependency: torch. Install with `pip install torch`.",
        }

    try:
        tokenizer, model = _get_or_load_model(
            repo_id=repo_id, hf_token=hf_token)
        inputs = tokenizer(prompt, return_tensors="pt")

        model_device = getattr(model, "device", None)
        if model_device is not None and hasattr(inputs, "to"):
            inputs = inputs.to(model_device)

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=True,
                temperature=TEMPERATURE,
                top_p=TOP_P,
            )

        decoded = tokenizer.decode(output[0], skip_special_tokens=True)
        completion = decoded[len(prompt):].strip(
        ) if decoded.startswith(prompt) else decoded.strip()
        prediction = _extract_prediction(
            completion, allowed_labels=allowed_labels)

        if prediction is None:
            return {
                "success": False,
                "query": query,
                "prompt": prompt,
                "prediction": None,
                "raw_output": decoded,
                "error": invalid_output_error,
            }

        return {
            "success": True,
            "query": query,
            "prompt": prompt,
            "prediction": prediction,
            "raw_output": decoded,
        }

    except ImportError:
        return {
            "success": False,
            "query": query,
            "prediction": None,
            "error": "Missing dependency: transformers. Install with `pip install transformers`.",
        }
    except Exception as e:
        return {
            "success": False,
            "query": query,
            "prediction": None,
            "error": f"{runtime_error_prefix}: {str(e)}",
        }


def predict_molecule_binding(
    smiles: Annotated[
        str,
        Field(description="Molecule SMILES string."),
    ],
    target: Annotated[
        str,
        Field(description="Target protein name/symbol."),
    ],
) -> Dict[str, Any]:
    """
    Predict molecule-target binding activity with fixed fine-tuned LLM settings.

    Output label semantics: 1 = active, 0 = inactive.
    """
    smiles = smiles.strip()
    target = target.strip()

    if not smiles:
        return {
            "success": False,
            "query": {},
            "prediction": None,
            "error": "smiles cannot be empty.",
        }
    if not target:
        return {
            "success": False,
            "query": {},
            "prediction": None,
            "error": "target cannot be empty.",
        }

    prompt = BINDING_PROMPT_TEMPLATE.format(smiles=smiles, target=target)
    result = _run_prediction(
        smiles=smiles,
        prompt=prompt,
        repo_id=BINDING_REPO_ID,
        allowed_labels={0, 1},
        invalid_output_error="Model output does not contain a valid 0/1 prediction.",
        runtime_error_prefix="Error running binding prediction",
    )
    result["query"]["target"] = target
    return result


def predict_molecule_synthesizability(
    smiles: Annotated[
        str,
        Field(description="Molecule SMILES string."),
    ],
) -> Dict[str, Any]:
    """
    Predict molecule synthesizability with fixed fine-tuned LLM settings.

    Output label semantics: 1 = yes, 0 = no, 2 = unknown.
    """
    smiles = smiles.strip()

    if not smiles:
        return {
            "success": False,
            "query": {},
            "prediction": None,
            "error": "smiles cannot be empty.",
        }

    prompt = SYNTHESIZABILITY_PROMPT_TEMPLATE.format(smiles=smiles)
    return _run_prediction(
        smiles=smiles,
        prompt=prompt,
        repo_id=SYNTHESIZABILITY_REPO_ID,
        allowed_labels={0, 1, 2},
        invalid_output_error="Model output does not contain a valid 0/1/2 prediction.",
        runtime_error_prefix="Error running synthesizability prediction",
    )
