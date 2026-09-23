import boto3, json, os, uuid, urllib.parse
from datetime import datetime, timezone

textract = boto3.client("textract")
dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses")

table = dynamodb.Table(os.environ["TABLE_NAME"])
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]

def text_of(field):
    v = field.get("ValueDetection", {})
    return v.get("Text", "") if isinstance(v, dict) else ""

def type_of(field):
    v = field.get("Type", {})
    return v.get("Text", "") if isinstance(v, dict) else ""

def lambda_handler(event, context):
    print("========== RECEIPT PROCESSOR STARTED ==========")
    print(json.dumps(event))

    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    receipt_id = str(uuid.uuid4())

    response = textract.analyze_expense(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    print("Textract processing completed.")

    docs = response.get("ExpenseDocuments", [])
    if not docs:
        raise Exception("Textract did not detect receipt information.")

    doc = docs[0]
    data = {
        "receipt_id": receipt_id,
        "s3_bucket": bucket,
        "s3_key": key,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "store_name": "",
        "receipt_date": "",
        "invoice_id": "",
        "vendor_phone": "",
        "vendor_address": "",
        "subtotal": "",
        "tax": "",
        "discount": "",
        "total": "",
        "payment_method": "",
        "tax_payer_id": "",
        "vendor_gst_number": "",
        "items": []
    }

    for field in doc.get("SummaryFields", []):
        t, v = type_of(field), text_of(field)
        print(f"Summary field: {t} = {v}")
        if t == "VENDOR_NAME" and not data["store_name"]: data["store_name"] = v
        elif t == "INVOICE_RECEIPT_DATE" and not data["receipt_date"]: data["receipt_date"] = v
        elif t == "INVOICE_RECEIPT_ID" and not data["invoice_id"]: data["invoice_id"] = v
        elif t == "TOTAL" and not data["total"]: data["total"] = v
        elif t == "SUBTOTAL" and not data["subtotal"]: data["subtotal"] = v
        elif t in ["TAX", "TOTAL_TAX"] and not data["tax"]: data["tax"] = v
        elif t == "DISCOUNT" and not data["discount"]: data["discount"] = v
        elif t == "PAYMENT_METHOD" and not data["payment_method"]: data["payment_method"] = v
        elif t == "VENDOR_PHONE" and not data["vendor_phone"]: data["vendor_phone"] = v
        elif t in ["VENDOR_ADDRESS", "ADDRESS"] and not data["vendor_address"]: data["vendor_address"] = v
        elif t == "TAX_PAYER_ID" and not data["tax_payer_id"]: data["tax_payer_id"] = v
        elif t == "VENDOR_GST_NUMBER" and not data["vendor_gst_number"]: data["vendor_gst_number"] = v

    for group in doc.get("LineItemGroups", []):
        for li in group.get("LineItems", []):
            item = {}
            for field in li.get("LineItemExpenseFields", []):
                t, v = type_of(field), text_of(field)
                if t == "ITEM": item["item"] = v
                elif t == "PRICE": item["price"] = v
                elif t == "QUANTITY": item["quantity"] = v
                elif t == "UNIT_PRICE": item["unit_price"] = v
            if item: data["items"].append(item)

    table.put_item(Item=data)
    print("Receipt successfully stored in DynamoDB.")
    print("Receipt data:")
    print(json.dumps(data, indent=2))

    lines = []
    for i, item in enumerate(data["items"], 1):
        lines.append(
            f"Item {i}: {item.get('item','N/A')} | Qty: {item.get('quantity','N/A')} | Unit Price: {item.get('unit_price','N/A')} | Price: {item.get('price','N/A')}"
        )
    items = "\n".join(lines) if lines else "No line items detected."

    body = f"""Receipt Processing Summary

Receipt ID: {receipt_id}

STORE INFORMATION
Store Name: {data['store_name']}
Vendor Phone: {data['vendor_phone']}
Vendor Address: {data['vendor_address']}

RECEIPT INFORMATION
Receipt Date: {data['receipt_date']}
Invoice / Receipt ID: {data['invoice_id']}
Payment Method: {data['payment_method']}

TAX INFORMATION
Tax Payer ID: {data['tax_payer_id']}
Vendor GST Number: {data['vendor_gst_number']}

FINANCIAL INFORMATION
Subtotal: {data['subtotal']}
Discount: {data['discount']}
Tax: {data['tax']}
TOTAL: {data['total']}

ITEMS
{items}

AWS INFORMATION
S3 Bucket: {bucket}
S3 File: {key}
Processed At: {data['processed_at']}

Receipt processed successfully by AWS.
"""

    print("Sending receipt summary email...")
    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [RECIPIENT_EMAIL]},
        Message={
            "Subject": {"Data": "Receipt Processing Summary"},
            "Body": {"Text": {"Data": body}}
        }
    )
    print("Receipt summary email sent successfully.")
    print("========== RECEIPT PROCESSOR FINISHED ==========")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Receipt processed successfully", "receipt_id": receipt_id})
    }
