### CMS in memory


DB = {
    "rules": [],
    "invoices": {},
    "emails": [],
    "products": {
        "SKU-205": {"name": "AGI course 101 Personal", "price": 258},
        "SKU-210": {"name": "AGI 101 Course Team", "price": 1290},
        "SKU-220": {"name": "Building AGI - Online Excercises", "price": 315}
    }
}


### Tool Definitions
from typing import List, Union, Literal, Annotated
from annotated_types import MaxLen, Le, MinLen
from pydantic import BaseModel, Field

# Note: Equivalent to function definition
class SendEmail(BaseModel):
    tool: Literal["send_email"]
    subject: str
    message: str
    files: List[str]
    recipient_email: str



class GetCustomerData(BaseModel):
    """Gets customer data from our DB"""
    tool: Literal['get_customer_data']
    email: str


class IssueInvoice(BaseModel):
    """Issues invoice for the customer and specific skus"""
    tool: Literal['issue_invoice']
    email: str
    skus: List[str]
    discount_percent: Annotated[int, Le(50)] # never more than 50%


class CancelInvoice(BaseModel):
    """Cancels invoice with provided reason"""
    tool: Literal["cancel_invoice"]
    invoice_id: str
    reason: str



class CreateRule(BaseModel):
    """Saves a custom rule for interacting with a customer"""
    tool: Literal['remember']
    email: str
    rule: str


# This function handles executing commands issued by the agent. It simulates  
# operations like sending emails, managing invoices, and updating customer  
# rules within the in-memory database. 

### Dispatch function implementation
def dispatch(cmd: BaseModel):

    ### Sending email
    if isinstance(cmd, SendEmail):
        email = {
            'to': cmd.recipient_email,
            'subject': cmd.subject,
            'message': cmd.message
        }

        DB['emails'].append(email)
        return email

    ### Implementation of the rest of the handlers

    ### Rule creation
    if isinstance(cmd, CreateRule):
        rule = {
            "email": cmd.email,
            "rule": cmd.rule
        }
        DB['rules'].append(rule)
        return rule
    
    ### Get customer data queries the DB
    if isinstance(cmd, GetCustomerData):
        addr = cmd.email
        return {
            "rules": [r for r in DB['rules'] if r['email'] == addr],
            "invoices": [inv for inv in DB['invoices'].items() if inv[1]['email'] == addr],
            "emails": [em for em in DB['emails'] if em.get("to") == addr]
        }

    ### Issue invoice
    if isinstance(cmd, IssueInvoice):
        total = 0.0
        for sku in cmd.skus:
            product = DB['products'].get(sku)
            if not product:
                return f"Product {sku} not found"
            total += product['price']

        discount = round(total * 1.0 * discount / 100.0, 2)

        invoice_id = f"INV-{len(DB['invoices']) + 1}"

        invoice = {
            "id": invoice_id,
            "email": cmd.email,
            "file": "/invoices" + invoice_id + ".pdf",
            "skus": cmd.skus,
            "discount_amount": discount,
            "discount_percent": cmd.discount_percent,
            "total": total,
            "void": False
        }
        
        DB['invoices'][invoice_id] = invoice
        return invoice

    if isinstance(cmd, CancelInvoice):
        invoice = DB['invoices'].get(cmd.invoice_id)
        if not invoice:
            return f"Invoice {cmd.invoice_id} not found"
        invoice['void'] = True
        return invoice


### Test Tasks - https://abdullin.com/schema-guided-reasoning/demo
TEST_TASKS = [

    # TODO: Copy tasks here
]


### Task Termination Command
class ReportTaskCompletion(BaseModel):
    tool: Literal['report_completion']
    completed_steps_laconic: List[str]
    code: Literal['completed', 'failed']



### Prompt Engineering

class NextStep(BaseModel):
    pass

SYSTEM_PROMPT = """


"""