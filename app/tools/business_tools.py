"""Mock business data: customers and orders (deterministic, no database needed)."""
from app.errors import ToolError
from app.tools.registry import ToolRegistry, ToolSpec

CUSTOMERS = {
    "C001": {"customer_id": "C001", "first_name": "Sammi", "last_name": "Shahi",
             "email": "sammishahi.shahi@gmail.com", "city": "Ahmedabad"},
    "C002": {"customer_id": "C002", "first_name": "Mohit", "last_name": "Raj",
             "email": "mraj08@gmail.com", "city": "Ahmedabad"},
    "C003": {"customer_id": "C003", "first_name": "sachin", "last_name": "Maurya",
             "email": "", "city": "Delhi"},  # empty email: useful for validation demos
}

ORDERS = {
    "ORD-1001": {"order_id": "ORD-1001", "customer_id": "C001", "amount": 75000, "currency": "INR"},
    "ORD-1002": {"order_id": "ORD-1002", "customer_id": "C002", "amount": 12000, "currency": "INR"},
}


def get_customer(params: dict) -> dict:
    cid = str(params["customer_id"]).strip().upper()
    if cid not in CUSTOMERS:
        raise ToolError(f"Customer '{cid}' not found. Known: {sorted(CUSTOMERS)}", retryable=False)
    return dict(CUSTOMERS[cid])


def get_order(params: dict) -> dict:
    oid = str(params["order_id"]).strip().upper()
    if oid not in ORDERS:
        raise ToolError(f"Order '{oid}' not found. Known: {sorted(ORDERS)}", retryable=False)
    return dict(ORDERS[oid])


def register_tools(registry: ToolRegistry) -> None:
    registry.register(ToolSpec(
        name="get_customer", category="tool",
        description="Looks up a customer. Returns {customer_id, first_name, last_name, email, city}. "
                    "Known ids: C001, C002, C003.",
        params={"customer_id": "e.g. C001"}, required=["customer_id"], func=get_customer,
    ))
    registry.register(ToolSpec(
        name="get_order", category="tool",
        description="Looks up an order. Returns {order_id, customer_id, amount (INR number), currency}. "
                    "Known ids: ORD-1001 (75000), ORD-1002 (12000).",
        params={"order_id": "e.g. ORD-1001"}, required=["order_id"], func=get_order,
    ))
