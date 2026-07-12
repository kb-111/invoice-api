
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
from dateutil import parser


app = FastAPI()


# ---------------------------
# CORS
# ---------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------
# Request Model
# ---------------------------

class InvoiceRequest(BaseModel):
    invoice_text: str



# ---------------------------
# Helpers
# ---------------------------

def normalize_amount(value):

    if value is None:
        return None

    value = value.replace(",", "")
    value = re.sub(r"[^\d.]", "", value)

    try:
        return float(value)

    except:
        return None



# ---------------------------
# Invoice Number
# ---------------------------

def extract_invoice(text):

    patterns = [

        r"Invoice\s*(?:No|Number|#)\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)",

        r"Invoice\s*[:\-]\s*([A-Za-z0-9\/\-_]+)",

        r"Bill\s*(?:No|Number|#)\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)",

        r"Ref\s*[:\-]\s*([A-Za-z0-9\/\-_]+)",

        r"Reference\s*[:\-]\s*([A-Za-z0-9\/\-_]+)"
    ]


    for p in patterns:

        m = re.search(
            p,
            text,
            re.IGNORECASE
        )

        if m:
            return m.group(1).strip()


    return None




# ---------------------------
# Date
# ---------------------------

def extract_date(text):

    patterns = [

        r"Date\s*[:\-]\s*([A-Za-z0-9,\-/ ]+)",

        r"Issued\s*[:\-]\s*([A-Za-z0-9,\-/ ]+)",

        r"Invoice Date\s*[:\-]\s*([A-Za-z0-9,\-/ ]+)"
    ]


    for p in patterns:

        m = re.search(
            p,
            text,
            re.IGNORECASE
        )

        if m:

            try:

                dt = parser.parse(
                    m.group(1)
                )

                return dt.strftime("%Y-%m-%d")

            except:
                pass


    return None




# ---------------------------
# Vendor
# ---------------------------

def extract_vendor(text):


    patterns = [

        r"Vendor\s*[:\-]\s*(.+)",

        r"Seller\s*[:\-]\s*(.+)",

        r"Supplier\s*[:\-]\s*(.+)",

        r"From\s*[:\-]\s*(.+)"
    ]


    for p in patterns:

        m = re.search(
            p,
            text,
            re.IGNORECASE
        )

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


        return first.strip(
            " -—:"
        )



    return None




# ---------------------------
# Amount/Subtotal
# ---------------------------

def extract_amount(text):
    patterns = [
        r"Subtotal\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
        r"Sub\s*Total\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
        r"Taxable\s*(?:Amount|Value)\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
        r"Amount\s*Before\s*Tax\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
        r"Base\s*Amount\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
        r"Net\s*Amount\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return normalize_amount(m.group(1))

    # Fallback: amount = total - tax
    total_match = re.search(
        r"(?:Grand\s*Total|Total\s*Due|Invoice\s*Total|Total)\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )

    tax = extract_tax(text)

    if total_match and tax is not None:
        total = normalize_amount(total_match.group(1))
        if total is not None:
            return total - tax

    return None


# ---------------------------
# Tax
# ---------------------------

def extract_tax(text):


    patterns = [

        # GST Amount: 440
        r"(?:GST|Tax|VAT|IGST|CGST|SGST)\s*Amount\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+\.?\d*)",


        # GST @ 18% : 440
        r"(?:GST|Tax|VAT|IGST|CGST|SGST)\s*@\s*\d+\s*%\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+\.?\d*)",


        # GST (18%): 440
        r"(?:GST|Tax|VAT|IGST|CGST|SGST)\s*\(\s*\d+\s*%\s*\)\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+\.?\d*)",


        # GST: 440
        r"(?:GST|Tax|VAT|IGST|CGST|SGST)\s*[:=\-]\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+\.?\d*)",


        # Total Tax
        r"Total\s+Tax\s*[:=\-]?\s*(?:Rs\.?|INR|USD|\$)?\s*([\d,]+\.?\d*)"

    ]


    for p in patterns:

        m = re.search(
            p,
            text,
            re.IGNORECASE
        )


        if m:

            return normalize_amount(
                m.group(1)
            )



    # CGST + SGST case

    cgst = re.search(
        r"CGST.*?([\d,]+\.?\d*)",
        text,
        re.IGNORECASE
    )

    sgst = re.search(
        r"SGST.*?([\d,]+\.?\d*)",
        text,
        re.IGNORECASE
    )


    if cgst and sgst:

        cgst_amount = normalize_amount(cgst.group(1))
        sgst_amount = normalize_amount(sgst.group(1))

        if cgst_amount is not None and sgst_amount is not None:
            return cgst_amount + sgst_amount


    return None



# ---------------------------
# Currency
# ---------------------------

def extract_currency(text):


    m = re.search(
        r"Currency\s*[:\-]\s*([A-Z]{3})",
        text,
        re.IGNORECASE
    )


    if m:

        return m.group(1).upper()



    for c in [
        "INR",
        "USD",
        "EUR",
        "GBP"
    ]:

        if c in text:

            return c



    if "₹" in text or "Rs" in text:

        return "INR"



    return None




# ---------------------------
# API
# ---------------------------

@app.get("/")
def home():

    return {
        "status":"Invoice API running"
    }



@app.post("/extract")
def extract(req: InvoiceRequest):


    text = req.invoice_text


    return {

        "invoice_no": extract_invoice(text),

        "date": extract_date(text),

        "vendor": extract_vendor(text),

        "amount": extract_amount(text),

        "tax": extract_tax(text),

        "currency": extract_currency(text)

    }
