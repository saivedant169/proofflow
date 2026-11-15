"""Create local-only credentials without printing them or overwriting existing ones."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
state = root / ".state"
state.mkdir(exist_ok=True)
token_file = state / "hydra-token"
if not token_file.exists():
    token_file.write_text(secrets.token_urlsafe(36) + "\n")
    token_file.chmod(0o644)  # mounted read-only into the non-root local container
env_file = root / ".env"
if not env_file.exists():
    env_file.write_text("PROOFFLOW_HYDRA_URL=http://127.0.0.1:18443\n"
                        f"PROOFFLOW_HYDRA_TOKEN={token_file.read_text().strip()}\n")
    env_file.chmod(0o600)
print("Local credentials ready; values withheld.")
