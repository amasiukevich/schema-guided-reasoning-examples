# =============================================
#  CMS in memory

import json
from typing import Annotated, List, Literal, Union

from annotated_types import Le, MaxLen, MinLen
from pydantic import BaseModel, Field

# using rich for pretty-printing in the console
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

# Import model providers
from common.models import create_model_provider, get_model_name

DB = {
    "rules": [],
    "invoices": {},
    "emails": [],
    "products": {
        "SKU-205": {"name": "AGI course 101 Personal", "price": 258},
        "SKU-210": {"name": "AGI 101 Course Team", "price": 1290},
        "SKU-220": {"name": "Building AGI - Online Excercises", "price": 315},
    },
}


# ==========================================
# Tool calls
class SendEmail(BaseModel):
    tool: Literal["send_email"]
    subject: str
    message: str
    files: List[str]
    recipient_email: str


class GetCustomerData(BaseModel):
    """Gets customer data from our DB"""

    tool: Literal["get_customer_data"]
    email: str


class IssueInvoice(BaseModel):
    """Issues invoice for the customer and specific skus"""

    tool: Literal["issue_invoice"]
    email: str
    skus: List[str]
    discount_percent: Annotated[int, Le(50)]  # never more than 50%


class CancelInvoice(BaseModel):
    """Cancels invoice with provided reason"""

    tool: Literal["cancel_invoice"]
    invoice_id: str
    reason: str


class CreateRule(BaseModel):
    """Saves a custom rule for interacting with a customer"""

    tool: Literal["remember"]
    email: str
    rule: str


# This function handles executing commands issued by the agent. It simulates
# operations like sending emails, managing invoices, and updating customer
# rules within the in-memory database.


# ========================================
# Dispatch function implementation
def dispatch(cmd: BaseModel):

    # ======================================
    # Sending email
    if isinstance(cmd, SendEmail):
        email = {"to": cmd.recipient_email, "subject": cmd.subject, "message": cmd.message}

        DB["emails"].append(email)
        return email

    # ============================================
    # Implementation of the rest of the handlers

    # ============================================
    # Rule creation
    if isinstance(cmd, CreateRule):
        rule = {"email": cmd.email, "rule": cmd.rule}
        DB["rules"].append(rule)
        return rule

    # ============================================
    # Get customer data queries the DB
    if isinstance(cmd, GetCustomerData):
        addr = cmd.email
        return {
            "rules": [r for r in DB["rules"] if r["email"] == addr],
            "invoices": [inv for inv in DB["invoices"].items() if inv[1]["email"] == addr],
            "emails": [em for em in DB["emails"] if em.get("to") == addr],
        }

    # ============================================
    # Issue invoice
    if isinstance(cmd, IssueInvoice):
        total = 0.0
        for sku in cmd.skus:
            product = DB["products"].get(sku)
            if not product:
                return f"Product {sku} not found"
            total += product["price"]

        discount = round(total * 1.0 * cmd.discount_percent / 100.0, 2)

        invoice_id = f"INV-{len(DB['invoices']) + 1}"

        invoice = {
            "id": invoice_id,
            "email": cmd.email,
            "file": "/invoices" + invoice_id + ".pdf",
            "skus": cmd.skus,
            "discount_amount": discount,
            "discount_percent": cmd.discount_percent,
            "total": total,
            "void": False,
        }

        DB["invoices"][invoice_id] = invoice
        return invoice

    if isinstance(cmd, CancelInvoice):
        invoice = DB["invoices"].get(cmd.invoice_id)
        if not invoice:
            return f"Invoice {cmd.invoice_id} not found"
        invoice["void"] = True
        return invoice


# ==============================================================
#  Test Tasks - https://abdullin.com/schema-guided-reasoning/demo
TEST_TASKS = [
    # 1. Should create a new rule for SAMA
    "Rule: address sama@openai.com as 'The SAMA', always give him 5% discount",
    # 2. Should create a rule for Elon
    "Rule for elon@x.com. Email his invoices to finances@x.com",
    # 3. Email for SAMA for each product
    "sama@openai.com wants one of each product. Email him the invoice",
    # 4. Evem more tricky
    "elon@x.com wants 2x the way sama@openai.com got. Send the invoice",
    # 5. Even more tricky - with discounts
    "redo last elon@x.com invoice: use 3x discount of sama@openai.com",
]


# ==============================================
# Task Termination Command
class ReportTaskCompletion(BaseModel):
    tool: Literal["report_completion"]
    completed_steps_laconic: List[str]
    code: Literal["completed", "failed"]


# ==============================================
# Prompt Engineering
class NextStep(BaseModel):

    # some thinking space here
    current_task: str

    # cycle to think about what remains to be done. At least 1 to 5 steps
    # we'll only use the 1st step, discarding the rest
    plan_remaining_steps_brief: Annotated[List[str], MinLen(1), MaxLen(5)]

    # checking if the task is done
    task_completed: bool

    function: Union[ReportTaskCompletion, CancelInvoice, IssueInvoice, GetCustomerData, SendEmail, CreateRule] = Field(
        ..., description="Execute first remaining step"
    )


# ==============================================
#  All of the products are loaded into one system prompt - the bigger the prompt - maybe loading tools conditionally
SYSTEM_PROMPT = f"""
    You're a business assistant helping Anton with customer interactions.

    - Clearly report when tasks are done
    - Always send customer emails after issuing invoices (with invoices attached)
    - Be concise, especially in the emails
    - No need for payment confirmation before processing
    - Always check customer data before issuing invoices or makeing changes

    Products: {DB['products']}
""".strip()


# ===============================================
# Tasks Processing

console = Console()
print = console.print

# Initialize model provider
model_provider = create_model_provider()
model_name = get_model_name()


def execute_tasks():

    # ==============================================
    # we are executing tasks sequentially.

    for task in TEST_TASKS:
        print("\n\n")
        print(Panel(task, title="Launch agent with task", title_align="left"))

        log = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]

        # Up to 20 reasoning steps
        for i in range(20):
            step = f"step_{i+1}"
            print(f"Planning {step}... ", end="")
            print(model_name)
            completion = model_provider.chat_completion(
                model=model_name,
                response_format=NextStep,
                messages=log,
                max_completion_tokens=1000,
            )

            # Parse JSON response manually since OpenRouter returns JSON as string
            response_content = completion.choices[0].message.content
            job_dict = json.loads(response_content)
            job = NextStep.model_validate(job_dict)

            if isinstance(job.function, ReportTaskCompletion):
                print(f"[blue]agent {job.function.code}[/blue].")
                print(Rule("Summary"))
                for s in job.function.completed_steps_laconic:
                    print(f"- {s}")
                print(Rule())
                break

            print(job.plan_remaining_steps_brief[0], f"\n  {job.function}")

            log.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "type": "function",
                            "id": step,
                            "function": {"name": job.function.tool, "arguments": job.function.model_dump_json()},
                        }
                    ],
                }
            )

            result = dispatch(job.function)
            txt = result if isinstance(result, str) else json.dumps(result)

            log.append({"role": "tool", "content": txt, "tool_call_id": step})


if __name__ == "__main__":
    execute_tasks()
