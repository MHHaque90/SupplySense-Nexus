"""Initial schema.

Revision ID: initial
Revises: 
Create Date: 2026-09-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='analyst'),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'product_categories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, index=True),
        sa.Column('parent_id', sa.String(36), sa.ForeignKey('product_categories.id'), nullable=True, index=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'warehouses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('location', sa.String(255), nullable=False),
        sa.Column('capacity_units', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_utilization', sa.String(5), nullable=False, server_default='0.00'),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'suppliers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('country', sa.String(100), nullable=False),
        sa.Column('rating', sa.String(3), nullable=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'products',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sku', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category_id', sa.String(36), sa.ForeignKey('product_categories.id'), nullable=True, index=True),
        sa.Column('unit_cost', sa.String(10), nullable=True),
        sa.Column('weight_kg', sa.String(8), nullable=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'bills_of_materials',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'bom_components',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('bom_id', sa.String(36), sa.ForeignKey('bills_of_materials.id'), nullable=False, index=True),
        sa.Column('component_product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('quantity', sa.String(12), nullable=False),
        sa.Column('unit_of_measure', sa.String(50), nullable=False),
        sa.Column('lead_time_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'inventory_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('available_qty', sa.String(12), nullable=False, server_default='0'),
        sa.Column('reserved_qty', sa.String(12), nullable=False, server_default='0'),
        sa.Column('in_transit_qty', sa.String(12), nullable=False, server_default='0'),
        sa.Column('snapshot_date', sa.Date(), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('transaction_type', sa.String(50), nullable=False, index=True),
        sa.Column('quantity', sa.String(12), nullable=False),
        sa.Column('reference_id', sa.String(36), nullable=True),
        sa.Column('timestamp', sa.Date(), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'supplier_products',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('supplier_id', sa.String(36), sa.ForeignKey('suppliers.id'), nullable=False, index=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('unit_cost', sa.String(10), nullable=False, server_default='0'),
        sa.Column('lead_time_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('min_order_qty', sa.String(12), nullable=False, server_default='1'),
        sa.Column('moq_currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('capacity_units', sa.String(12), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'purchase_orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('supplier_id', sa.String(36), sa.ForeignKey('suppliers.id'), nullable=False, index=True),
        sa.Column('po_number', sa.String(50), nullable=False, index=True),
        sa.Column('order_date', sa.Date(), nullable=False, index=True),
        sa.Column('expected_delivery_date', sa.Date(), nullable=True),
        sa.Column('total_cost', sa.String(12), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending', index=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'purchase_order_lines',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('po_id', sa.String(36), sa.ForeignKey('purchase_orders.id'), nullable=False, index=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('quantity', sa.String(12), nullable=False),
        sa.Column('unit_cost', sa.String(10), nullable=False),
        sa.Column('line_total', sa.String(12), nullable=False, server_default='0'),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'shipments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('po_id', sa.String(36), sa.ForeignKey('purchase_orders.id'), nullable=False, index=True),
        sa.Column('supplier_id', sa.String(36), sa.ForeignKey('suppliers.id'), nullable=False, index=True),
        sa.Column('shipped_date', sa.Date(), nullable=True),
        sa.Column('expected_arrival_date', sa.Date(), nullable=False),
        sa.Column('actual_arrival_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending', index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'shipment_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('shipment_id', sa.String(36), sa.ForeignKey('shipments.id'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'sales_orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('customer_id', sa.String(36), nullable=False),
        sa.Column('order_date', sa.Date(), nullable=False, index=True),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('total_amount', sa.String(12), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending', index=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'sales_order_lines',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sales_order_id', sa.String(36), sa.ForeignKey('sales_orders.id'), nullable=False, index=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('quantity', sa.String(12), nullable=False),
        sa.Column('unit_price', sa.String(10), nullable=False),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'demand_observations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('date', sa.Date(), nullable=False, index=True),
        sa.Column('quantity', sa.String(12), nullable=False),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'model_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('model_name', sa.String(100), nullable=False, index=True),
        sa.Column('model_type', sa.String(100), nullable=False),
        sa.Column('version', sa.String(20), nullable=False, index=True),
        sa.Column('training_window_start', sa.Date(), nullable=True),
        sa.Column('training_window_end', sa.Date(), nullable=True),
        sa.Column('metrics', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('registered_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
        sa.Index('idx_mv_model_name_active', 'model_name', 'is_active'),
        sa.Index('idx_mv_model_name_version', 'model_name', 'version'),
    )
    op.create_table(
        'forecasts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('forecast_date', sa.Date(), nullable=False, index=True),
        sa.Column('point_estimate', sa.String(12), nullable=False),
        sa.Column('lower_bound', sa.String(12), nullable=False),
        sa.Column('upper_bound', sa.String(12), nullable=False),
        sa.Column('model_version_id', sa.String(36), sa.ForeignKey('model_versions.id'), nullable=True, index=True),
        sa.Column('confidence_level', sa.String(5), nullable=False, server_default='0.95'),
        sa.Column('forecast_horizon_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='simulated'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'forecast_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('model_version_id', sa.String(36), sa.ForeignKey('model_versions.id'), nullable=False, index=True),
        sa.Column('run_timestamp', sa.Date(), nullable=False),
        sa.Column('training_window_start', sa.Date(), nullable=True),
        sa.Column('training_window_end', sa.Date(), nullable=True),
        sa.Column('validation_metrics', sa.Text(), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='derived'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'disruptions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('disruption_type', sa.String(100), nullable=False, index=True),
        sa.Column('severity', sa.String(50), nullable=False, server_default='medium'),
        sa.Column('start_date', sa.Date(), nullable=False, index=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('affected_supplier_id', sa.String(36), sa.ForeignKey('suppliers.id'), nullable=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='simulated'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'disruption_impacts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('disruption_id', sa.String(36), sa.ForeignKey('disruptions.id'), nullable=False, index=True),
        sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=False, index=True),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('estimated_demand_shortfall', sa.String(12), nullable=False, server_default='0'),
        sa.Column('estimated_cost_impact', sa.String(12), nullable=False, server_default='0'),
        sa.Column('stockout_probability', sa.String(5), nullable=False, server_default='0'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'scenarios',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scenario_type', sa.String(100), nullable=False, server_default='baseline', index=True),
        sa.Column('base_assumptions', sa.Text(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=False, server_default='42'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='simulated'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'decision_options',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('scenarios.id'), nullable=False, index=True),
        sa.Column('option_type', sa.String(50), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parameters', sa.Text(), nullable=True),
        sa.Column('estimated_cost', sa.String(12), nullable=False, server_default='0'),
        sa.Column('estimated_service_level', sa.String(5), nullable=False, server_default='0'),
        sa.Column('estimated_stockout_risk', sa.String(5), nullable=False, server_default='0'),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='simulated'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'scenario_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('scenarios.id'), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('magnitude', sa.String(10), nullable=False, server_default='0'),
        sa.Column('duration_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('affected_product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=True, index=True),
        sa.Column('affected_warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=True, index=True),
        sa.Column('affected_supplier_id', sa.String(36), sa.ForeignKey('suppliers.id'), nullable=True, index=True),
        sa.Column('probability', sa.String(5), nullable=False, server_default='0.0'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'scenario_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('scenarios.id'), nullable=False, index=True),
        sa.Column('decision_option_id', sa.String(36), sa.ForeignKey('decision_options.id'), nullable=False, index=True),
        sa.Column('expected_cost', sa.String(12), nullable=False, server_default='0'),
        sa.Column('expected_service_level', sa.String(5), nullable=False, server_default='0'),
        sa.Column('stockout_risk', sa.String(5), nullable=False, server_default='0'),
        sa.Column('inventory_impact', sa.Text(), nullable=True),
        sa.Column('supplier_exposure', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.String(5), nullable=False, server_default='0'),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='simulated'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'decision_comparisons',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('scenarios.id'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('baseline_option_id', sa.String(36), sa.ForeignKey('decision_options.id'), nullable=False),
        sa.Column('alternative_option_id', sa.String(36), sa.ForeignKey('decision_options.id'), nullable=False),
        sa.Column('cost_difference', sa.String(12), nullable=False, server_default='0'),
        sa.Column('service_difference', sa.String(5), nullable=False, server_default='0'),
        sa.Column('risk_difference', sa.String(5), nullable=False, server_default='0'),
        sa.Column('recommendation_rank', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confidence_score', sa.String(5), nullable=False, server_default='0'),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='simulated'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'optimization_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('scenarios.id'), nullable=False, index=True),
        sa.Column('objective', sa.String(100), nullable=False),
        sa.Column('solver_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('objective_value', sa.String(15), nullable=False, server_default='0'),
        sa.Column('solution', sa.Text(), nullable=True),
        sa.Column('constraint_violations', sa.Text(), nullable=True),
        sa.Column('solver_time_seconds', sa.String(10), nullable=False, server_default='0'),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='simulated'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )
    op.create_table(
        'data_quality_checks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('table_name', sa.String(100), nullable=False, index=True),
        sa.Column('check_type', sa.String(100), nullable=False, index=True),
        sa.Column('check_rule', sa.Text(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checked_at', sa.Date(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
        sa.Index('idx_dqc_table_checked_at', 'table_name', 'checked_at'),
        sa.Index('idx_dqc_passed', 'passed'),
    )
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=True, index=True),
        sa.Column('parameters', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('timestamp', sa.Date(), nullable=False, index=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
        sa.Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        sa.Index('idx_audit_entity', 'entity_type', 'entity_id'),
        sa.Index('idx_audit_timestamp', 'timestamp'),
    )


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('data_quality_checks')
    op.drop_table('optimization_runs')
    op.drop_table('decision_comparisons')
    op.drop_table('decision_options')
    op.drop_table('scenario_results')
    op.drop_table('scenario_events')
    op.drop_table('scenarios')
    op.drop_table('disruption_impacts')
    op.drop_table('disruptions')
    op.drop_table('forecast_runs')
    op.drop_table('forecasts')
    op.drop_table('model_versions')
    op.drop_table('demand_observations')
    op.drop_table('sales_order_lines')
    op.drop_table('sales_orders')
    op.drop_table('shipment_events')
    op.drop_table('shipments')
    op.drop_table('purchase_order_lines')
    op.drop_table('purchase_orders')
    op.drop_table('supplier_products')
    op.drop_table('inventory_transactions')
    op.drop_table('inventory_snapshots')
    op.drop_table('bom_components')
    op.drop_table('bills_of_materials')
    op.drop_table('products')
    op.drop_table('suppliers')
    op.drop_table('warehouses')
    op.drop_table('product_categories')
    op.drop_table('users')
    op.drop_table('organizations')
