"""Fix remaining ForeignKey constraints in forecast, scenario, governance."""

# Fix forecast.py
with open('backend/app/models/forecast.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, Text',
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, Text, ForeignKey'
)
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)
c = c.replace(
    'warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)'
)
c = c.replace(
    'model_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)',
    'model_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_versions.id"), nullable=True, index=True)'
)
# ForecastRun model_version_id
c = c.replace(
    'model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'model_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("model_versions.id"), nullable=False, index=True)'
)
# DisruptionImpact
c = c.replace(
    'disruption_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'disruption_id: Mapped[str] = mapped_column(String(36), ForeignKey("disruptions.id"), nullable=False, index=True)'
)
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)
c = c.replace(
    'warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)'
)
# Disruption affected_supplier_id
c = c.replace(
    'affected_supplier_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)',
    'affected_supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True, index=True)'
)

with open('backend/app/models/forecast.py', 'w') as f:
    f.write(c)

# Fix scenario.py
with open('backend/app/models/scenario.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, Text, Boolean',
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, Text, Boolean, ForeignKey'
)
# Scenario created_by
c = c.replace(
    'created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)'
)
# ScenarioEvent scenario_id
c = c.replace(
    'scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)'
)
# ScenarioResult scenario_id and decision_option_id
c = c.replace(
    'scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)'
)
c = c.replace(
    'decision_option_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'decision_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_options.id"), nullable=False, index=True)'
)
# DecisionOption scenario_id
c = c.replace(
    'scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)'
)
# DecisionComparison
c = c.replace(
    'scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)'
)
c = c.replace(
    'baseline_option_id: Mapped[str] = mapped_column(String(36), nullable=False)',
    'baseline_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_options.id"), nullable=False)'
)
c = c.replace(
    'alternative_option_id: Mapped[str] = mapped_column(String(36), nullable=False)',
    'alternative_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_options.id"), nullable=False)'
)
# OptimizationRun scenario_id
c = c.replace(
    'scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)'
)

with open('backend/app/models/scenario.py', 'w') as f:
    f.write(c)

# Fix governance.py
with open('backend/app/models/governance.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, Text, Boolean',
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, Text, Boolean, ForeignKey'
)
# ModelVersion registered_by
c = c.replace(
    'registered_by: Mapped[str] = mapped_column(String(36), nullable=False)',
    'registered_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)'
)
# AuditEvent user_id
c = c.replace(
    'user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)'
)

with open('backend/app/models/governance.py', 'w') as f:
    f.write(c)

print("Fixed forecast.py, scenario.py, governance.py")
