"""Fix remaining ForeignKey constraints in model files."""

# Fix procurement.py
with open('backend/app/models/procurement.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index',
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, ForeignKey'
)
c = c.replace(
    'supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)'
)
c = c.replace(
    'po_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'po_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True)'
)
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)
c = c.replace(
    'shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'shipment_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)'
)
c = c.replace(
    'warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)'
)
# Fix PurchaseOrder organization_id
c = c.replace(
    'organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)'
)
# Fix SalesOrder warehouse_id
c = c.replace(
    'warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)'
)

with open('backend/app/models/procurement.py', 'w') as f:
    f.write(c)

# Fix sales.py
with open('backend/app/models/sales.py') as f:
    c = f.read()

c = c.replace(
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index',
    'from sqlalchemy import String, DECIMAL, Integer, Date, Index, ForeignKey'
)
# warehouse_id in SalesOrder
c = c.replace(
    'warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)'
)
# product_id in SalesOrderLine
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)
# sales_order_id in SalesOrderLine
c = c.replace(
    'sales_order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'sales_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=False, index=True)'
)
# product_id and warehouse_id in DemandObservation
c = c.replace(
    'product_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)'
)
c = c.replace(
    'warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)'
)
# organization_id in SalesOrder
c = c.replace(
    'organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)',
    'organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)'
)

with open('backend/app/models/sales.py', 'w') as f:
    f.write(c)

print("Fixed procurement.py and sales.py")
