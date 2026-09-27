"""
Unified interface for calling any model in the MODELS registry (see
config.py). Every experiment script should call llm_clients.call_llm(...)
instead of instantiating its own API client -- this is the ONE place that
knows how to talk to Claude vs. a VT ARC-hosted model.
"""

import os
from lib.config import MODELS


def call_llm(model_key, system_prompt, user_prompt, max_tokens=512, temperature=None, reasoning_effort=None):
    """
    Returns the model's raw text response (str), or None on failure.
    model_key: one of the keys in config.MODELS (e.g. "claude", "glm-5.2-thinking").
    reasoning_effort: optional "low"/"medium"/"high" -- only meaningful for
        openai_compatible (VT ARC) models that support it; ignored for
        Claude. Lower effort trades reasoning depth for reliability/speed --
        confirmed via VT ARC's own docs as a real, supported parameter.
    """
    if model_key not in MODELS:
        raise ValueError(f"Unknown model_key '{model_key}'. Known models: {list(MODELS.keys())}")

    cfg = MODELS[model_key]
    api_key = os.environ.get(cfg["api_key_env"])
    if not api_key:
        raise RuntimeError(
            f"Missing API key for model '{model_key}': "
            f"set the {cfg['api_key_env']} environment variable."
        )

    if cfg["backend"] == "anthropic_native":
        return _call_anthropic(api_key, cfg["model_id"], system_prompt, user_prompt, max_tokens)
    elif cfg["backend"] == "openai_compatible":
        return _call_openai_compatible(
            api_key, cfg["base_url"], cfg["model_id"], system_prompt, user_prompt,
            max_tokens, temperature, reasoning_effort
        )
    else:
        raise ValueError(f"Unknown backend '{cfg['backend']}' for model '{model_key}'")


def _call_anthropic(api_key, model_id, system_prompt, user_prompt, max_tokens):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # concatenate all text blocks in case of multi-block responses
    return "".join(block.text for block in response.content if hasattr(block, "text"))


def _call_openai_compatible(api_key, base_url, model_id, system_prompt, user_prompt, max_tokens, temperature, reasoning_effort=None):
    """
    Uses streaming rather than a plain request-and-wait call. VT ARC's own
    documentation states that non-streaming requests with long outputs are
    more likely to time out. Streaming avoids that timeout; we still
    return the fully accumulated text at the end, so nothing calling this
    function needs to change.
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort

    stream = client.chat.completions.create(
        model=model_id,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
        **kwargs,
    )

    chunks = []
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            chunks.append(delta.content)

    return "".join(chunks)


if __name__ == "__main__":
    # quick smoke test -- run with: python3 -m lib.llm_clients <model_key> [reasoning_effort]
    import sys
    model_key = sys.argv[1] if len(sys.argv) > 1 else "claude"
    effort = sys.argv[2] if len(sys.argv) > 2 else None
    print(f"Testing model_key='{model_key}' reasoning_effort={effort!r}...")
    result = call_llm(
        model_key,
        system_prompt="You are a helpful assistant.",
        user_prompt="Reply with exactly the word: OK",
        max_tokens=1024,
        reasoning_effort=effort,
    )
    print(f"Response: {result!r}")

