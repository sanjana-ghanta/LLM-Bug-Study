"""
Central configuration for the pipeline. To add a new Defects4J project or a
new model, add an entry here -- nothing else in the pipeline should need to
change.
"""

import os

# ---------------------------------------------------------------------------
# PROJECTS: one entry per Defects4J project used in the study.
# src_candidates: possible source-root prefixes to try when locating a file
#   inside a checkout (different projects lay out their source tree
#   differently -- this list is tried in order until one exists).
# repo_name: the .git directory name under ~/defects4j/project_repos/,
#   used for full-history checks (git log -L, later-commit analysis, etc).
# ---------------------------------------------------------------------------
PROJECTS = {
    "Chart": {
        "defects4j_name": "Chart",
        "repo_name": "jfreechart",
        "src_candidates": ["source", "src", "src/main/java", ""],
    },
    "Lang": {
        "defects4j_name": "Lang",
        "repo_name": "commons-lang",
        "src_candidates": ["src/main/java", "src", "source", ""],
    },
    "Math": {
        "defects4j_name": "Math",
        "repo_name": "commons-math",
        "src_candidates": ["src/main/java", "src", "source", ""],
    },
    "Time": {
        "defects4j_name": "Time",
        "repo_name": "joda-time",
        "src_candidates": ["src/main/java", "src", "source", ""],
    },
    "Mockito": {
        "defects4j_name": "Mockito",
        "repo_name": "mockito",
        "src_candidates": ["src/main/java", "src", "source", ""],
    },
    # To add a new project (e.g. Time, Closure, Mockito), add an entry here:
    # "Time": {
    #     "defects4j_name": "Time",
    #     "repo_name": "joda-time",
    #     "src_candidates": ["src/main/java", "src", "source", ""],
    # },
}

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUGS_DIR = os.path.join(BASE, "data/bugs")
REPO_DIR = os.path.expanduser("~/defects4j/project_repos")
RESULTS_DIR = os.path.join(BASE, "results/java")


def results_csv_path(project, suffix=""):
    """Standardized results file naming: results_<suffix>_<project>.csv"""
    name = f"results_{suffix}_{project.lower()}.csv" if suffix else f"results_{project.lower()}.csv"
    return os.path.join(RESULTS_DIR, name)


# ---------------------------------------------------------------------------
# MODELS: one entry per model available to the pipeline.
# backend: "anthropic_native" (direct Anthropic API) or "openai_compatible"
#   (any OpenAI-compatible endpoint, e.g. VT ARC's llm-api.arc.vt.edu).
# api_key_env: name of the environment variable holding the API key --
#   never hardcode keys here.
# model_id: the exact model string the backend expects. For VT ARC models,
#   verify the exact id via `client.models.list()` once you have a key --
#   the names below are best-guesses and may need correcting.
# ---------------------------------------------------------------------------
MODELS = {
    "claude": {
        "backend": "anthropic_native",
        "model_id": "claude-sonnet-4-6",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    # NOTE: the exact model requested ("GLM-5.2 Thinking") is not available
    # on VT ARC as of the model list pulled -- only GLM-5.3 is offered.
    # Using the closest available match; flag this substitution in the paper.
    "glm-5.3-thinking": {
        "backend": "openai_compatible",
        "base_url": "https://llm-api.arc.vt.edu/api/v1",
        "model_id": "GLM-5.3-thinking-high",
        "api_key_env": "VT_ARC_API_KEY",
    },
    # NOTE: VT ARC only offers the "Flash" (smaller/faster) variant of
    # DeepSeek V4, not the full-size model. Worth noting explicitly in the
    # paper's model description since this is not the same claim as
    # "DeepSeek V4 Thinking".
    "deepseek-v4-flash-thinking": {
        "backend": "openai_compatible",
        "base_url": "https://llm-api.arc.vt.edu/api/v1",
        "model_id": "DeepSeek-V4.1-Flash-thinking-max",
        "api_key_env": "VT_ARC_API_KEY",
    },
    "gpt-oss-thinking": {
        "backend": "openai_compatible",
        "base_url": "https://llm-api.arc.vt.edu/api/v1",
        "model_id": "gpt-oss-120b-thinking-high",
        "api_key_env": "VT_ARC_API_KEY",
    },
    # To add another model, add an entry here. Any OpenAI-compatible
    # endpoint (VT ARC or otherwise) just needs backend/base_url/model_id/
    # api_key_env -- no other code changes needed.
}

