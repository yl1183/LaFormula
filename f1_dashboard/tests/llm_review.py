"""LLM-based code review using 4 frontier models.
Each reviewer validates the trading system logic, autonomy, and safety."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import litellm

PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "https://mines-ai.com/litellm/v1")
API_KEY = os.environ.get("LITELLM_PROXY_API_KEY", "")

MODELS = {
    "gemini": os.environ.get("LITELLM_MODEL_GEMINI", "gemini-3.1-pro"),
    "gpt": os.environ.get("LITELLM_MODEL_GPT", "gpt-5.2"),
    "sonnet": os.environ.get("LITELLM_MODEL_SONNET", "sonnet-4.6"),
    "opus": os.environ.get("LITELLM_MODEL_OPUS", "opus-4.6"),
}

# Load all source code for review
def load_file(path):
    try:
        with open(path) as f:
            return f.read()
    except:
        return f"[File not found: {path}]"

SOURCE_FILES = {
    "config.py": load_file("../backend/config.py"),
    "strategy.py": load_file("../backend/strategy.py"),
    "db.py": load_file("../backend/db.py"),
    "main.py": load_file("../backend/main.py"),
    "kalshi_client.py": load_file("../backend/kalshi_client.py"),
    "f1_live.py": load_file("../backend/f1_live.py"),
}

REVIEW_PROMPT = """You are reviewing an autonomous F1 prediction market trading system for Kalshi.
The system must:
1. Run 24/7 autonomously — no human confirmation for trades
2. Monitor Kalshi F1 markets (poll every 5 min during race weekends)
3. After qualifying results are available, generate signals using 3 sleeves:
   - Sleeve A: Buy YES podium when base_rate - price >= 15%
   - Sleeve B: Buy NO winner when price - base_rate >= 8% for P2/P3 starters
   - Sleeve E: Buy NO winner when price - base_rate >= 10%, price in [15%, 50%], grid > P3
4. Auto-place trades with risk caps: 7% per trade, 15% per weekend, halt at 50% drawdown
5. Kill switch: POST /api/kill?pin=483291 halts all new trades
6. Bankroll synced from Kalshi API; first 4 races at half-size
7. 2025 backtest: 30 trades, 67% win rate, $100→$226, 7.5% max drawdown

Here is the complete source code:

"""

for name, code in SOURCE_FILES.items():
    REVIEW_PROMPT += f"\n### {name}\n```python\n{code}\n```\n"

REVIEW_PROMPT += """

Please review this system and answer:
1. Is the trading logic correct? (Sleeves A, B, E thresholds, sizing, risk caps)
2. Is the autonomous loop properly structured? (No human confirmation, auto-starts on boot)
3. Are the safety rails correct? (Kill switch, drawdown halt, weekend cap, calibration period)
4. Is the Kalshi integration properly abstracted for dry-run vs live? (Will it work plug-and-play when API key is provided?)
5. Any bugs, race conditions, or logic errors?

Respond with a JSON object:
{
  "pass": true/false,
  "score": 1-10,
  "critical_issues": ["list of issues that must be fixed"],
  "warnings": ["non-critical concerns"],
  "summary": "one paragraph overall assessment"
}
"""

def review_with_model(model_name, model_id):
    """Send review prompt to a single model."""
    try:
        response = litellm.completion(
            model=f"openai/{model_id}",
            messages=[{"role": "user", "content": REVIEW_PROMPT}],
            api_base=PROXY_URL,
            api_key=API_KEY,
            timeout=120,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        # Try to extract JSON from response
        try:
            # Find JSON block
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            elif "{" in content:
                start = content.index("{")
                end = content.rindex("}") + 1
                json_str = content[start:end]
            else:
                json_str = content
            result = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            result = {"pass": None, "score": None, "raw_response": content[:2000]}
        
        result["model"] = model_name
        return result
    except Exception as e:
        return {"model": model_name, "pass": None, "score": None, "error": str(e)}


def main():
    os.chdir(os.path.dirname(__file__))
    
    results = {}
    passes = 0
    total = 0
    
    for name, model_id in MODELS.items():
        print(f"\n{'='*60}")
        print(f"Reviewing with {name} ({model_id})...")
        print(f"{'='*60}")
        
        result = review_with_model(name, model_id)
        results[name] = result
        total += 1
        
        if result.get("pass"):
            passes += 1
            print(f"  ✅ PASS (score: {result.get('score', '?')}/10)")
        elif result.get("pass") is False:
            print(f"  ❌ FAIL (score: {result.get('score', '?')}/10)")
        else:
            print(f"  ⚠️ UNCLEAR")
        
        if result.get("critical_issues"):
            for issue in result["critical_issues"]:
                print(f"  🔴 {issue}")
        if result.get("warnings"):
            for w in result["warnings"][:3]:
                print(f"  🟡 {w}")
        if result.get("summary"):
            print(f"  📝 {result['summary'][:200]}")
        if result.get("error"):
            print(f"  ⚠️ Error: {result['error']}")
    
    print(f"\n{'='*60}")
    print(f"FINAL: {passes}/{total} reviewers passed")
    print(f"{'='*60}")
    
    # Save results
    with open("/workspace/f1_dashboard/tests/review_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return passes, total, results


if __name__ == "__main__":
    passes, total, results = main()
