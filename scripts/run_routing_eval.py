"""Development wrapper for the self-contained tessera-eval runner."""

from pathlib import Path
import runpy


RUNNER = (
    Path(__file__).resolve().parents[1]
    / "pieces"
    / "tessera-core"
    / "skills"
    / "tessera-eval"
    / "scripts"
    / "run_routing_eval.py"
)


if __name__ == "__main__":
    runpy.run_path(str(RUNNER), run_name="__main__")
