"""Optimization Engine (Phase 10).

Deterministic, auditable MILP-based procurement optimization built strictly
on public Phase 9 Decision Replay outputs. Consumes Phase 8 event mechanics
unchanged, adds no database schema, and labels every output as synthetic /
simulated planning data.

Public surface:

- ``build_optimization_inputs``: Phase 9 -> Phase 10 adapter (documented
  contract in ``docs/optimization-engine.md``).
- ``build_formulation``: MILP construction for one of the four declared
  objectives.
- ``OptimizationSolver`` / ``ScipyHiGHSSolver``: solver abstraction and the
  installed SciPy/HiGHS backend.
- ``validate_result``: independent result validation.
- ``run_optimization``: full orchestration returning a run payload.
- ``build_report`` / ``render_markdown``: the 21-section reporting contract.
"""

from backend.app.analytics.optimization.comparison import (
    build_baseline_comparison,
    build_scenario_comparison,
    evaluate_plan,
)
from backend.app.analytics.optimization.inputs import (
    build_optimization_inputs,
)
from backend.app.analytics.optimization.optimization import run_optimization
from backend.app.analytics.optimization.problem import build_formulation
from backend.app.analytics.optimization.reports import (
    REPORT_SECTIONS,
    SECTION_TITLES,
    build_report,
    render_markdown,
)
from backend.app.analytics.optimization.solver import (
    OptimizationSolver,
    ScipyHiGHSSolver,
)
from backend.app.analytics.optimization.types import (
    DEFAULT_OPTIMIZATION_CONFIG,
    OBJECTIVES,
    STATUSES,
    Constraint,
    DecisionVariable,
    Objective,
    OptimizationConfig,
    OptimizationProblem,
    OptimizationResult,
    ProblemFormulation,
    Provenance,
)
from backend.app.analytics.optimization.validation import validate_result

__all__ = [
    "DEFAULT_OPTIMIZATION_CONFIG",
    "OBJECTIVES",
    "REPORT_SECTIONS",
    "SECTION_TITLES",
    "STATUSES",
    "Constraint",
    "DecisionVariable",
    "Objective",
    "OptimizationConfig",
    "OptimizationProblem",
    "OptimizationResult",
    "OptimizationSolver",
    "ProblemFormulation",
    "Provenance",
    "ScipyHiGHSSolver",
    "build_baseline_comparison",
    "build_formulation",
    "build_optimization_inputs",
    "build_report",
    "build_scenario_comparison",
    "evaluate_plan",
    "render_markdown",
    "run_optimization",
    "validate_result",
]
