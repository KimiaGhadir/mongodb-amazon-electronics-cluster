"""Static sanity checks for the TA-required Docker topology."""
from pathlib import Path

compose = Path(__file__).resolve().parents[1] / "docker-compose.yml"
text = compose.read_text(encoding="utf-8")
required = [
    "mongo1:", "mongo2:", "mongo3:", "mongo-init:", "dev:",
    "image: mongo:7", "--replSet rs0", "27017:27017", "27018:27017",
    "27019:27017", 'host: "mongo1:27017"', 'host: "mongo2:27017"',
    'host: "mongo3:27017"',
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("TA compatibility check failed; missing: " + ", ".join(missing))
print("TA compatibility check: OK")
