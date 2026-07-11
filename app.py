from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
from dateutil import parser

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


# -----------------------------
# Utility Functions
# -----------------------------

def normalize_amount(value):
    if value is None:
        return None

    value = value.replace(",", "")
    value = re.sub(r"[^\d.]", "", value)

    try:
        return float(value)
    except:
        return None


def extract_date(text):
    patterns = [
        r"Date[:\s]*([A-Za-z0-9,\-/ ]+)",
        r"Issued[:\s]*([A-Za-z0-9,\-/ ]+)",
        r"Invoice Date[:\s]*([A-Za-z0-9,\-/ ]+)",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                dt = parser.parse(m.group(1))
                return dt.strftime("%Y-%m-%d")
            except:
                pass

    return None


def extract_invoice(text):

    patterns = [
        r"Invoice\s*(?:No|Number|#)\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
        r"Ref\s*[:\-]\s*([A-Za-z0-9\-/]+)",
        r"Reference\s*[:\-]\s*([A-Za-z0-9\-/]+)"
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return None


def extract_vendor(text):

    patterns = [
        r"Vendor[:\s]*(.+)",
        r"Seller[:\s]*(.+)",
        r"From[:\s]*(.+)",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()


    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    if lines:
        first = lines[0]

        first = re.sub(
            r"Tax Invoice|Commercial Invoice|Invoice",
            "",
            first,
            flags=re.IGNORECASE
        )

        return first.strip(" -—")


    return None

def extract_currency(text):

    m = re.search(r"Currency[:\s]*([A-Z]{3})", text)

    if m:
        return m.group(1)

    for cur in ["INR", "USD", "EUR", "GBP", "JPY"]:
        if cur in text:
            return cur

    if "Rs." in text or "₹" in text:
        return "INR"

    return None


def extract_tax(text):

    # First priority: explicit tax amount labels
    patterns = [

        # Tax Amount: 440
        r"(?:Tax|GST|VAT|IGST|CGST|SGST)\s*Amount\s*[:\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",

        # GST Amount = 440
        r"(?:Tax|GST|VAT|IGST|CGST|SGST)\s*(?:Amount|Value)?\s*[:=\-]\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",

        # IGST (18%): 25200
        r"(?:IGST|CGST|SGST|GST|VAT)\s*\(\s*\d+\s*%\s*\)\s*[:\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",

        # GST @ 18% : 440
        r"(?:GST|Tax|VAT)\s*@\s*\d+\s*%\s*[:\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",

        # Simple Tax: 440
        r"\bTax\s*[:\-]\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
    ]


    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        for m in matches:
            value = normalize_amount(m)

            if value and value > 50:
                return value


    # Handle separate taxes
    cgst = re.search(
        r"CGST.*?([\d,]+(?:\.\d+)?)",
        text,
        re.IGNORECASE
    )

    sgst = re.search(
        r"SGST.*?([\d,]+(?:\.\d+)?)",
        text,
        re.IGNORECASE
    )


    if cgst and sgst:
        cgst_value = normalize_amount(cgst.group(1))
        sgst_value = normalize_amount(sgst.group(1))
        if cgst_value is not None and sgst_value is not None:
            return cgst_value + sgst_value


    return None

def extract_amount(text):

    patterns = [
        r"Subtotal[:\sA-Z₹$Rs.]*([\d,]+\.\d+)",
        r"Sub Total[:\sA-Z₹$Rs.]*([\d,]+\.\d+)",
        r"Amount[:\sA-Z₹$Rs.]*([\d,]+\.\d+)",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return normalize_amount(m.group(1))

    return None


@app.get("/")
def root():
    return {"status": "running"}


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    return {
        "invoice_no": extract_invoice(text),
        "date": extract_date(text),
        "vendor": extract_vendor(text),
        "amount": extract_amount(text),
        "tax": extract_tax(text),
        "currency": extract_currency(text),
    }