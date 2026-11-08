"""Fix all ForeignKey constraints in model files."""

# Fix bom.py
with open('backend/app/models/bom.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index',
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, ForeignKey'
)
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)
c = c.replace(
    'bom_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'bom_id: Mapped[str] = mapped_column(String(36), ForeignKey("bills_of_materials.id"), nullable=False, index=True)'
)
c = c.replace(
    'component_product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'component_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)

with open('backend/app/models/bom.py', 'w') as f:
    f.write(c)

# Fix inventory.py
with open('backend/app/models/inventory.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index',
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, ForeignKey'
)
c = c.replace(
    'organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)'
)
# Replace first two occurrences for warehouse_id and product_id
c = c.replace(
    'warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)'
)
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)

with open('backend/app/models/inventory.py', 'w') as f:
    f.write(c)

# Fix supplier.py
with open('backend/app/models/supplier.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Index',
    'from sqlalchemy import String, DECIMAL, Integer, Index, ForeignKey'
)
c = c.replace(
    'organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)'
)
c = c.replace(
    'supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)'
)
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)

with open('backend/app/models/supplier.py', 'w') as f:
    f.write(c)

print("Fixed bom.py, inventory.py, supplier.py")
