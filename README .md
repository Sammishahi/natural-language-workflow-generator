# 🔀 Natural Language Workflow Generator

> **A GenAI-powered workflow automation system that converts natural-language business requirements into validated, executable workflows.**

---

## 🎯 What does this project do?

Instead of manually defining every step of a business process, a user simply describes what they want in natural language.

### Example

**User:**
> Look up order ORD-1001. If the amount is greater than ₹50,000, request manager approval before sending a confirmation email. Otherwise send the email directly.

**System:**

```text
Natural Language Requirement
          ↓
      Cloud LLM
          ↓
   Structured JSON Workflow
          ↓
 Pydantic + Custom Validation
          ↓
    Workflow Engine
          ↓
      Tool Registry
          ↓
 APIs / Business Tools / Transformations
          ↓
       Final Result
```

The LLM is used for **planning**, while validation and execution remain controlled by the application.

---

## 🚀 Key Features

| Feature | Supported |
|---|:---:|
| Natural language → workflow | ✅ |
| Cloud LLM integration | ✅ |
| Structured JSON generation | ✅ |
| Pydantic schema validation | ✅ |
| Custom workflow validation | ✅ |
| LLM self-repair on invalid output | ✅ |
| Tool registry / allow-list | ✅ |
| API execution | ✅ |
| Data transformation | ✅ |
| Conditional branching | ✅ |
| Human approval | ✅ |
| Approval / rejection | ✅ |
| Retry mechanism | ✅ |
| Failure handling | ✅ |
| Runtime state & execution logs | ✅ |
| Real public API demo | ✅ |
| Streamlit UI | ✅ |
| Automated tests | ✅ |

---

# 🏗️ Architecture

```text
┌───────────────────────────────┐
│            User               │
│  Natural-language requirement │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│        Streamlit UI           │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│     Workflow Generator        │
│       (Cloud LLM)             │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│     Structured JSON           │
│        Workflow               │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│  Pydantic + Custom Validator  │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│       Workflow Engine         │
│ Conditions • Retry • Approval │
│ State • Error Handling        │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│        Tool Registry          │
│       Allow-listed tools      │
└───────────────┬───────────────┘
                ↓
     ┌──────────┼──────────┐
     ↓          ↓          ↓
   APIs      Business    Data /
             Tools       Transform
                ↓
        Execution Result
```

---

# 🧠 How the system works

### 1. User describes the requirement

The user enters a business requirement in the Streamlit interface.

Example:

> Get customer C001 and display the customer's email.

### 2. Cloud LLM generates a workflow

The LLM converts the requirement into structured JSON.

For example:

```json
{
  "workflow_name": "customer_email_lookup",
  "steps": [
    {
      "id": "get_customer",
      "type": "tool",
      "tool": "get_customer",
      "params": {
        "customer_id": "C001"
      },
      "output": "customer"
    },
    {
      "id": "show_email",
      "type": "tool",
      "tool": "display",
      "params": {
        "value": "{{customer.email}}"
      }
    }
  ]
}
```

### 3. Workflow is validated

Two layers of validation are used:

**Pydantic validation**
- Schema
- Required fields
- Step types
- IDs
- References
- Structural correctness

**Custom validation**
- Tool availability
- Required tool parameters
- Dependencies
- Output references
- Circular dependencies

### 4. Workflow is executed

The `WorkflowEngine` executes the validated steps.

It supports:

- Sequential execution
- Conditions
- API calls
- Transformations
- Retries
- Human approval
- Rejection
- Failure states
- Runtime context
- Execution logs

### 5. Tools are controlled

The LLM cannot execute arbitrary Python code.

It can only select tools registered in the `ToolRegistry`.

```text
LLM selects tool
       ↓
Tool Registry
       ↓
Is tool registered?
   ↙           ↘
 No            Yes
 ↓              ↓
Reject        Execute
```

This creates a controlled boundary between LLM planning and real execution.

---

# 🔐 Tool Registry & Security

The project uses an **allow-listed tool registry**.

Available tools include:

- `get_customer`
- `get_order`
- `http_get`
- `mock_api`
- `calculator`
- `concat_text`
- `extract_field`
- `add_field`
- `format_currency`
- `validate_required`
- `validate_email`
- `validate_number_range`
- `display`
- `send_email`

The real HTTP tool also restricts requests to configured hosts.

API credentials are loaded through environment variables and are not hardcoded in source code.

---

# 🔄 LLM Self-Repair

The application does not blindly trust the first LLM response.

```text
Generate workflow
       ↓
Pydantic validation
       ↓
Custom validation
       ↓
     Valid?
     /   \
   Yes    No
    ↓      ↓
   Run   Return validation
         errors to LLM
              ↓
       Generate corrected
           workflow
```

This helps handle cases where the LLM forgets a dependency, uses an invalid tool, or produces an incorrect workflow structure.

---

# ⚙️ Workflow Engine

The engine supports three main error strategies:

### `fail`

Stop the workflow when a step fails.

### `retry`

Retry retryable failures.

Example:

```text
API call
   ↓
Temporary failure
   ↓
Retry
   ↓
Success
```

### `continue`

Record the failure and continue where the workflow configuration allows it.

---

# 👤 Human Approval

The workflow engine supports human-in-the-loop execution.

Example:

```text
Check Order Amount
       ↓
 Amount > ₹50,000?
    ↙          ↘
  YES           NO
   ↓             ↓
Manager       Send Email
Approval       Directly
   ↓
Approve / Reject
   ↓
Continue / Stop
```

The workflow can enter:

```text
WAITING_FOR_APPROVAL
```

and resume after the approval decision.

---

# 🧪 Demonstrations

The project contains built-in scenarios covering the major capabilities.

### Demo 1 — Customer Email Lookup

Fetch customer information and display the email.

**Demonstrates:**
- Tool execution
- Output references
- Final display

### Demo 2 — High-Value Order Approval ⭐

If an order is above ₹50,000, ask for manager approval before sending the confirmation email.

**Demonstrates:**
- Business data lookup
- Conditional logic
- Human approval
- Branching
- Email tool
- Workflow resume

### Demo 3 — Data Transformation

Validate a customer's first and last name, create `full_name`, and display the updated record.

**Demonstrates:**
- Validation
- Transformation
- Dependent steps
- Data references

### Demo 4 — Retry Recovery

A mock API temporarily fails and then succeeds.

**Demonstrates:**
- Retry policy
- Retryable errors
- Attempt tracking

### Demo 5 — Persistent API Failure

A mock API keeps failing after retries.

**Demonstrates:**
- Retry exhaustion
- Error recording
- Final `FAILED` state

### Demo 6 — Real Public API

Calls:

```text
https://jsonplaceholder.typicode.com/users/1
```

and displays real user information.

**Demonstrates:**
- Real HTTP request
- API allow-list
- JSON response handling

---

# 📁 Project Structure

```text
workflow_generator/
│
├── app/
│   ├── engine/
│   │   ├── expressions.py
│   │   ├── validator.py
│   │   └── workflow_engine.py
│   │
│   ├── llm/
│   │   ├── prompts.py
│   │   └── workflow_generator.py
│   │
│   ├── models/
│   │   ├── run_state.py
│   │   └── workflow_schema.py
│   │
│   ├── tools/
│   │   ├── api_tools.py
│   │   ├── business_tools.py
│   │   ├── calculator.py
│   │   ├── data_tools.py
│   │   ├── email_tool.py
│   │   └── registry.py
│   │
│   ├── config.py
│   ├── errors.py
│   ├── main.py
│   └── samples.py
│
├── tests/
├── docs/
├── architecture.png
├── streamlit_app.py
├── requirements.txt
├── .env.example
└── README.md
```

---

# 🧩 Important Modules

| Module | Responsibility |
|---|---|
| `streamlit_app.py` | User interface |
| `workflow_generator.py` | Cloud LLM integration & workflow generation |
| `prompts.py` | LLM instructions |
| `workflow_schema.py` | Pydantic workflow schema |
| `validator.py` | Tool/reference/dependency validation |
| `workflow_engine.py` | Workflow execution |
| `registry.py` | Controlled tool registry |
| `api_tools.py` | HTTP/API tools |
| `business_tools.py` | Mock customer/order data |
| `data_tools.py` | Transformations & validations |
| `email_tool.py` | Mock email tool |
| `run_state.py` | Runtime state & execution logs |
| `config.py` | Environment configuration |
| `errors.py` | Custom exceptions |
| `samples.py` | Built-in demo workflows |

---

# 🛠️ Tech Stack

- **Python 3.10+**
- **Streamlit** — UI
- **Pydantic** — structured workflow validation
- **OpenAI-compatible Cloud LLM API** — workflow generation
- **HTTPX** — HTTP/API calls
- **Pytest** — automated testing
- **python-dotenv** — environment configuration

---

# ▶️ Setup

## 1. Create virtual environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Configure environment

Copy:

```text
.env.example
```

to:

```text
.env
```

Configure:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=your_model
LLM_TIMEOUT_SECONDS=60
MAX_GENERATION_ATTEMPTS=3
```

> **Never commit or submit `.env`. It contains the API key.**

---

# ▶️ Run the Application

From the project root:

```bash
streamlit run streamlit_app.py
```

Then open the local Streamlit URL displayed in the terminal.

---

# 🧪 Run Tests

```bash
python -m pytest -q
```

The current project test suite contains **44 passing tests**.

---

# 💻 CLI Usage

List available demos:

```bash
python -m app.main --list
```

Run a sample:

```bash
python -m app.main --sample 1
```

Generate a workflow from a custom requirement:

```bash
python -m app.main --prompt "Get customer C001 and display the customer's email."
```

---

# 📌 Example Use Cases

The architecture can be extended to workflows such as:

- Customer information lookup
- Order processing
- Approval workflows
- API data retrieval
- Data transformation
- Validation pipelines
- Notification workflows
- Internal business automation

---

# ⚠️ Current Limitations

This implementation is an **assessment/MVP project**, not a production deployment.

- Email sending is currently mocked.
- Business data is stored in memory.
- Workflow state is local.
- Authentication and user management are not included.
- Production monitoring/tracing is not included.

---

# 🚀 Future Improvements

A production version could add:

- Real email provider integration
- Database-backed business tools
- Authentication & role-based access control
- Persistent workflow state
- Distributed workers and queues
- More API integrations
- Workflow versioning
- Production monitoring and tracing
- Slack/Teams/email approval notifications
- LLM evaluation and additional guardrails

---

# 🎤 One-Minute Interview Explanation

> **"I built a GenAI-based Natural Language Workflow Generator. A user provides a business requirement in natural language, and a cloud LLM converts it into a structured JSON workflow. I validate that workflow using Pydantic and a custom validator for tool availability, parameters, references, dependencies, and cycles. The validated workflow is then executed by a state-based workflow engine through an allow-listed tool registry. The engine supports APIs, data transformations, conditional logic, retries, failures, and human approval with resume and rejection states. The key design decision was to use the LLM for planning while keeping actual execution deterministic and controlled."**

---

# 📦 Submission Checklist

Before creating the ZIP, make sure these are **NOT included**:

```text
.env
venv/
__pycache__/
*.pyc
```

Include:

```text
app/
tests/
docs/
streamlit_app.py
README.md
requirements.txt
.env.example
architecture.png
pytest.ini
```

---

## ✅ Project Status

**Assessment-ready MVP**

The complete flow has been tested through the Streamlit interface, including workflow generation, validation, conditional execution, human approval, retry handling, failure handling, and a real public API integration.
