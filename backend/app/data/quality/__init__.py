"""Data quality framework for SupplySense Nexus (Phase 2).

Checks return structured results with PASS / WARN / FAIL status and
INFO / LOW / MEDIUM / HIGH / CRITICAL severity. Results are persisted
to the ``data_quality_checks`` table by the report module.
"""

from backend.app.data.quality.checks import CheckResult, run_all_checks
from backend.app.data.quality.report import QualityReport, build_report, persist_results

__all__ = ["CheckResult", "QualityReport", "build_report", "persist_results", "run_all_checks"]
