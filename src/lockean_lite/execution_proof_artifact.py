from pathlib import Path

from lockean_lite.autonomous_cycle import (
    AutonomousTradeCycleResult,
)
from lockean_lite.visual_execution_proof import (
    render_execution_result_html,
)


def render_execution_proof_artifact(
    result: AutonomousTradeCycleResult,
) -> str:
    return render_execution_result_html(
        result
    )


def write_execution_proof_artifact(
    *,
    result: AutonomousTradeCycleResult,
    output_path: Path,
) -> Path:
    html = render_execution_proof_artifact(
        result
    )

    try:
        output_path.write_text(
            html,
            encoding="utf-8",
        )
    except OSError as error:
        raise ValueError(
            "execution_proof_output_write_failed"
        ) from error

    return output_path