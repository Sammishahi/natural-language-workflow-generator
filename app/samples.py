"""Built-in demo scenarios (requirement text + a reference workflow for offline demo mode)."""

SAMPLES: dict[str, dict] = {
    "1": {
        "title": "Demo 1 - Customer email lookup",
        "requirement": "Get customer information for customer C001 and display the customer's email.",
        "workflow": {
            "workflow_name": "customer_email_lookup",
            "description": "Fetch a customer and display their email.",
            "steps": [
                {"id": "get_customer", "type": "tool", "tool": "get_customer",
                 "params": {"customer_id": "C001"}, "output": "customer"},
                {"id": "show_email", "type": "tool", "tool": "display",
                 "params": {"label": "Customer email", "value": "{{customer.email}}"}},
            ],
        },
    },
    "2": {
        "title": "Demo 2 - High-value order needs manager approval",
        "requirement": ("Look up order ORD-1001. If the amount is greater than ₹50,000, request manager approval "
                        "before sending a confirmation email to the customer. Otherwise send the email directly."),
        "workflow": {
            "workflow_name": "high_value_order_approval",
            "description": "Orders above 50,000 INR need manager approval before the confirmation email.",
            "steps": [
                {"id": "get_order", "type": "tool", "tool": "get_order",
                 "params": {"order_id": "ORD-1001"}, "output": "order"},
                {"id": "get_customer", "type": "tool", "tool": "get_customer",
                 "params": {"customer_id": "{{order.customer_id}}"}, "output": "customer"},
                {"id": "format_amount", "type": "transform", "tool": "format_currency",
                 "params": {"amount": "{{order.amount}}"}, "output": "amount_text"},
                {"id": "check_amount", "type": "condition",
                 "condition": {"left": "{{order.amount}}", "operator": ">", "right": 50000},
                 "if_true": ["manager_approval", "send_email_approved", "show_approved"], "if_false": ["send_email_direct", "show_direct"]},
                {"id": "manager_approval", "type": "human_approval", "approver_role": "manager",
                 "message": "Manager approval required.\nOrder amount: {{amount_text}}"},
                {"id": "send_email_approved", "type": "tool", "tool": "send_email",
                 "depends_on": ["manager_approval"],
                 "params": {"to": "{{customer.email}}", "subject": "Order {{order.order_id}} confirmed",
                            "body": "Hello {{customer.first_name}}, your order of {{amount_text}} is approved and confirmed."}},
                {"id": "send_email_direct", "type": "tool", "tool": "send_email",
                 "params": {"to": "{{customer.email}}", "subject": "Order {{order.order_id}} confirmed",
                            "body": "Hello {{customer.first_name}}, your order of {{amount_text}} is confirmed."}},
                {"id": "show_approved", "type": "tool", "tool": "display", "depends_on": ["send_email_approved"],
                 "params": {"label": "Result", "value": "Approved by manager. Confirmation email sent to {{customer.email}}"}},
                {"id": "show_direct", "type": "tool", "tool": "display", "depends_on": ["send_email_direct"],
                 "params": {"label": "Result", "value": "No approval needed. Confirmation email sent to {{customer.email}}"}},
            ],
        },
    },
    "3": {
        "title": "Demo 3 - Transform first + last name into full_name",
        "requirement": ("Get customer C002, make sure first name and last name are present, "
                        "combine them into a full_name field and display the updated customer record."),
        "workflow": {
            "workflow_name": "build_full_name",
            "description": "Validate names, concatenate into full_name and display the record.",
            "steps": [
                {"id": "get_customer", "type": "tool", "tool": "get_customer",
                 "params": {"customer_id": "C002"}, "output": "customer"},
                {"id": "check_names", "type": "validation", "tool": "validate_required",
                 "params": {"values": {"first_name": "{{customer.first_name}}", "last_name": "{{customer.last_name}}"}}},
                {"id": "join_names", "type": "transform", "tool": "concat_text",
                 "params": {"parts": ["{{customer.first_name}}", "{{customer.last_name}}"], "separator": " "},
                 "depends_on": ["check_names"], "output": "full_name_text"},
                {"id": "add_full_name", "type": "transform", "tool": "add_field",
                 "params": {"record": "{{customer}}", "field": "full_name", "value": "{{full_name_text}}"},
                 "output": "customer_updated"},
                {"id": "show_record", "type": "tool", "tool": "display",
                 "params": {"label": "Customer with full_name", "value": "{{customer_updated}}"}},
            ],
        },
    },
    "4": {
        "title": "Demo 4 - Flaky API recovers after retry",
        "requirement": ("Fetch user 1 from the internal API (it may fail temporarily, so retry up to 2 times) "
                        "and display the user's name and email."),
        "workflow": {
            "workflow_name": "flaky_api_with_retry",
            "description": "The mock API fails once, the engine retries and succeeds.",
            "steps": [
                {"id": "fetch_user", "type": "api", "tool": "mock_api",
                 "params": {"endpoint": "users/1", "fail_times": 1},
                 "on_error": {"strategy": "retry", "max_retries": 2, "retry_delay_seconds": 0.5},
                 "output": "user_response"},
                {"id": "show_name", "type": "tool", "tool": "display",
                 "params": {"label": "Name", "value": "{{user_response.data.name}}"}},
                {"id": "show_email", "type": "tool", "tool": "display",
                 "params": {"label": "Email", "value": "{{user_response.data.email}}"}},
            ],
        },
    },
    "5": {
        "title": "Demo 5 - API keeps failing -> workflow FAILED",
        "requirement": ("Fetch user 2 from the internal API with up to 2 retries. "
                        "The service is down, so show a clear error when it keeps failing."),
        "workflow": {
            "workflow_name": "api_failure_demo",
            "description": "The mock API always fails; after retries the workflow ends as FAILED.",
            "steps": [
                {"id": "fetch_user", "type": "api", "tool": "mock_api",
                 "params": {"endpoint": "users/2", "fail_times": 99},
                 "on_error": {"strategy": "retry", "max_retries": 2, "retry_delay_seconds": 0.5},
                 "output": "user_response"},
                {"id": "show_name", "type": "tool", "tool": "display",
                 "params": {"label": "Name", "value": "{{user_response.data.name}}"}},
            ],
        },
    },
    "6": {
        "title": "Demo 6 - Real public API (needs internet)",
        "requirement": "Fetch user 1 from https://jsonplaceholder.typicode.com/users/1 and display the name and company.",
        "workflow": {
            "workflow_name": "public_api_user",
            "description": "Calls a real public API with retry.",
            "steps": [
                {"id": "fetch_user", "type": "api", "tool": "http_get",
                 "params": {"url": "https://jsonplaceholder.typicode.com/users/1"},
                 "on_error": {"strategy": "retry", "max_retries": 2, "retry_delay_seconds": 1},
                 "output": "user_response"},
                {"id": "show_name", "type": "tool", "tool": "display",
                 "params": {"label": "Name", "value": "{{user_response.data.name}}"}},
                {"id": "show_company", "type": "tool", "tool": "display",
                 "params": {"label": "Company", "value": "{{user_response.data.company.name}}"}},
            ],
        },
    },
}
