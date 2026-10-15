import sys, os, json; sys.path.insert(0, "scripts")
from lib.config import MODELS
from openai import OpenAI
cap = int(sys.argv[1]); folder = sys.argv[2]   # e.g. 12000 pandas_8
cfg = MODELS["deepseek-v4-flash-thinking"]
client = OpenAI(api_key=os.environ[cfg["api_key_env"]], base_url=cfg["base_url"])
j = json.load(open(f"data/pybugs/{folder}/data.json"))
code = j["patched_code"]; c = j["original_bug_line"]; lines = code.splitlines()
if len(lines) > 120:
    code = "\n".join(lines[max(0, c-61):min(len(lines), c+60)])
prompt = f"""Review the following Python code from {j['file_path']} and determine if it contains a bug.
Respond in this exact format:
VERDICT: BUG or NO BUG
REASON: <one sentence explanation>

Code:
{code}"""
stream = client.chat.completions.create(model=cfg["model_id"], max_tokens=cap, reasoning_effort="low",
    messages=[{"role": "system", "content": "You are a careful code reviewer."}, {"role": "user", "content": prompt}],
    stream=True, stream_options={"include_usage": True})
ans, reas, fin, usage = [], [], None, None
for ch in stream:
    if getattr(ch, "usage", None): usage = ch.usage
    if not ch.choices: continue
    d = ch.choices[0].delta
    if d.content: ans.append(d.content)
    r = getattr(d, "reasoning_content", None) or getattr(d, "reasoning", None)
    if r: reas.append(r)
    if ch.choices[0].finish_reason: fin = ch.choices[0].finish_reason
A, R = "".join(ans), "".join(reas)
print("finish", fin, "| usage", usage, "| answer chars", len(A), "| reasoning chars", len(R))
print("--- answer ---"); print(A[:400])
print("--- reasoning (last 600 chars) ---"); print(R[-600:])
