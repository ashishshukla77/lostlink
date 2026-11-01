import os
import sys
from pathlib import Path

project = Path(__file__).resolve().parent
sys.path.insert(0, str(project / ".packages"))

from sarvamai import SarvamAI

# Load the project .env without requiring an extra dependency.
if not os.environ.get("SARVAM_API_KEY"):
    env_file = project / ".env"
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("SARVAM_API_KEY="):
            os.environ["SARVAM_API_KEY"] = line.partition("=")[2].strip().strip("\"'")
            break

client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Say hello in one short sentence."}],
)
print(response.choices[0].message.content)
