"""Fix migration file to add user_id and new FK columns."""

with open('backend/app/migrations/versions/initial_schema.py') as f:
    content = f.read()

# Add user_id to decision_comparisons
old = "        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('scenarios.id'), nullable=False, index=True),\n        sa.Column('baseline_option_id'"
new = "        sa.Column('scenario_id', sa.String(36), sa.ForeignKey('scenarios.id'), nullable=False, index=True),\n        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True, index=True),\n        sa.Column('baseline_option_id'"
content = content.replace(old, new)

# Update scenario_events to use new columns
old_events = "        sa.Column('magnitude', sa.String(10), nullable=False, server_default='0'),\n        sa.Column('duration_days', sa.Integer(), nullable=False, server_default='0'),\n        sa.Column('affected_entity_id', sa.String(36), nullable=True),\n        sa.Column('probability', sa.String(5), nullable=False, server_default='0.0'),"
new_events = "        sa.Column('magnitude', sa.String(10), nullable=False, server_default='0'),\n        sa.Column('duration_days', sa.Integer(), nullable=False, server_default='0'),\n        sa.Column('affected_product_id', sa.String(36), sa.ForeignKey('products.id'), nullable=True, index=True),\n        sa.Column('affected_warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id'), nullable=True, index=True),\n        sa.Column('affected_supplier_id', sa.String(36), sa.ForeignKey('suppliers.id'), nullable=True, index=True),\n        sa.Column('probability', sa.String(5), nullable=False, server_default='0.0'),"
content = content.replace(old_events, new_events)

with open('backend/app/migrations/versions/initial_schema.py', 'w') as f:
    f.write(content)
print('Migration updated')
