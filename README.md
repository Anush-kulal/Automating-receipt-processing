# Automating Receipt Processing with AWS

A serverless AWS project that automatically processes receipt images, extracts structured information with Amazon Textract, stores the results in DynamoDB, and sends a detailed receipt summary through Amazon SES.

## Architecture

```text
User
  |
  | Upload receipt image
  v
Amazon S3
  |
  | ObjectCreated event
  v
AWS Lambda (Python)
  |
  +--> Amazon Textract (AnalyzeExpense)
  |       +--> Store / vendor
  |       +--> Receipt date / invoice ID
  |       +--> Subtotal / tax / total
  |       +--> Address / phone / GST / tax IDs
  |       +--> Line items
  |
  +--> Amazon DynamoDB
  |       +--> ReceiptData
  |
  +--> Amazon SES
          +--> Detailed receipt summary email

CloudWatch Logs -> Lambda monitoring and debugging
IAM            -> Service permissions
```

## AWS Services

- **Amazon S3** — stores receipt images
- **AWS Lambda** — event-driven Python processing
- **Amazon Textract** — receipt/invoice extraction using `AnalyzeExpense`
- **Amazon DynamoDB** — stores structured receipt data
- **Amazon SES** — sends the receipt summary email
- **IAM** — controls Lambda permissions
- **Amazon CloudWatch** — logs and troubleshooting

## Repository Structure

```text
.
├── lambda_function.py
└── README.md
```

## Prerequisites

- AWS account
- AWS Region selected consistently; this project was tested in `ap-south-1` (Mumbai)
- Verified sender and recipient identities in Amazon SES
- Receipt image in PNG/JPG format
- Basic AWS Console knowledge

## Step 1 — Create the S3 Bucket

Create a private bucket, for example:

```text
receipt-processing-project
```

Keep **Block Public Access** enabled.

Create a prefix/folder:

```text
receipts/
```

Upload receipt images into this prefix.

## Step 2 — Create DynamoDB

Create a table:

- Table name: `ReceiptData`
- Partition key: `receipt_id`
- Type: `String`
- Capacity mode: `On-demand`
- No sort key required

## Step 3 — Create the Lambda IAM Role

Create an IAM role trusted by Lambda. The role needs permissions for:

- Reading receipt objects from S3
- `textract:AnalyzeExpense`
- `dynamodb:PutItem` for the `ReceiptData` table
- CloudWatch Logs
- `ses:SendEmail`

For a production deployment, prefer resource-scoped policies instead of broad managed policies.

### SES policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SendReceiptEmail",
      "Effect": "Allow",
      "Action": ["ses:SendEmail"],
      "Resource": "*"
    }
  ]
}
```

### DynamoDB policy

Replace `ACCOUNT_ID` with the AWS account ID:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "WriteReceiptData",
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem"],
      "Resource": "arn:aws:dynamodb:ap-south-1:ACCOUNT_ID:table/ReceiptData"
    }
  ]
}
```

### Textract policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AnalyzeReceipt",
      "Effect": "Allow",
      "Action": ["textract:AnalyzeExpense"],
      "Resource": "*"
    }
  ]
}
```

Also attach the standard CloudWatch Logs permissions required by the Lambda execution role and S3 read permission for the receipt bucket.

## Step 4 — Create Lambda

Create:

```text
Function name: ReceiptProcessor
Runtime: Python
Architecture: x86_64
Memory: 256 MB
Timeout: 1 minute
```

Attach the IAM role created above.

## Step 5 — Environment Variables

Add:

```text
TABLE_NAME=ReceiptData
SENDER_EMAIL=your-verified-sender@example.com
RECIPIENT_EMAIL=your-verified-recipient@example.com
```

Do not hard-code credentials or secrets into the source code.

## Step 6 — Add the Lambda Code

Open the Lambda code editor, copy `lambda_function.py` from this repository, and deploy it.

## Step 7 — Add the S3 Trigger

Add an S3 trigger to `ReceiptProcessor`:

- Bucket: `receipt-processing-project`
- Event: **All object create events**
- Prefix: `receipts/`

The prefix limits processing to receipt uploads.

## Step 8 — Configure SES

In the same AWS Region:

1. Verify the sender email identity.
2. Verify the recipient email if the SES account is still in sandbox.
3. Put the verified addresses into the Lambda environment variables.

The project can use different Gmail accounts for sender and recipient as long as the required SES identities are verified.

## Step 9 — Test the Workflow

Upload a new receipt to:

```text
s3://receipt-processing-project/receipts/test-receipt.png
```

Expected flow:

```text
S3 upload
   ↓
S3 ObjectCreated event
   ↓
Lambda
   ↓
Textract AnalyzeExpense
   ↓
DynamoDB
   ↓
SES
   ↓
Detailed email
```

## Step 10 — Verify the Result

### CloudWatch

Open:

```text
CloudWatch
  → Logs
  → /aws/lambda/ReceiptProcessor
```

A successful execution should include messages such as:

```text
Textract processing completed.
Receipt successfully stored in DynamoDB.
Receipt summary email sent successfully.
```

### DynamoDB

Open the `ReceiptData` table and inspect the new item. It can contain:

- `store_name`
- `receipt_date`
- `invoice_id`
- `vendor_phone`
- `vendor_address`
- `subtotal`
- `tax`
- `discount`
- `total`
- `payment_method`
- `tax_payer_id`
- `vendor_gst_number`
- `items`
- S3 bucket/key
- processing timestamp

### Email

The recipient receives a **Receipt Processing Summary** containing the extracted receipt information and line items when Textract detects them.

## Troubleshooting

### Lambda syntax/runtime error

Check Python indentation, Lambda runtime, IAM permissions, and redeploy.

### DynamoDB fields are empty

Check CloudWatch logs. Textract returns fields such as `Type` and `ValueDetection` as structured objects. The helper functions in `lambda_function.py` convert them to text before mapping the fields.

### Email not received

Check:

1. Sender identity is verified in SES.
2. Recipient identity is verified when SES is in sandbox.
3. Lambda has `ses:SendEmail` permission.
4. Check Gmail Spam/Promotions.
5. Check CloudWatch for `Receipt summary email sent successfully.`

## Security Notes

- Keep the S3 bucket private.
- Never commit AWS access keys, secret keys, passwords, or other credentials.
- Use IAM roles instead of hard-coded AWS credentials.
- Do not commit real receipts containing personal or financial information.
- SES identities are Region-specific.
- Clean up AWS resources after testing if cost control is important.

## Example Result

A successfully processed receipt can produce data similar to:

```text
Store: FreshMart
Date: 23-09-2026
Subtotal: 463.00
Tax: 11.58
Total: 486.16
Payment: UPI (PhonePe)
```

## Future Improvements

- HTML email template
- Textract confidence scores
- Store raw Textract JSON in S3
- SQS/EventBridge retry and failure handling
- Receipt history dashboard
- S3 lifecycle policies

## License

Educational and portfolio use.
