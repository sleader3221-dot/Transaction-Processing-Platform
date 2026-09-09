# CSV Upload Guide - Sample Files & Instructions

## 📁 Sample CSV Files Provided

We've created 3 ready-to-use sample CSV files in your project directory:

### 1. **sample_transactions.csv** (8 transactions)
General-purpose test file with mixed currencies and accounts.
- Accounts: ACC-USER-001, ACC-USER-002, ACC-USER-003
- Currencies: USD, EUR, GBP
- Good for: Quick testing

### 2. **invoicing_batch.csv** (10 transactions)
Invoicing scenario with multiple accounts and large amounts.
- Accounts: ACC-INVOICING-01, ACC-INVOICING-02, ACC-INVOICING-03
- Currencies: USD, EUR, GBP
- Good for: Batch processing testing

### 3. **daily_transactions.csv** (9 transactions)
Daily transaction feed with smaller amounts.
- Accounts: ACC-DAILY-A, ACC-DAILY-B, ACC-DAILY-C
- Currencies: USD, EUR, GBP
- Good for: Regular processing testing

---

## 📋 CSV File Format (Required)

Every CSV file must have this header row:
```
transaction_id,account_id,type,amount,currency,timestamp
```

Required columns:
- **transaction_id**: Unique identifier (e.g., TXN-001, INV-JUNE-001)
- **account_id**: Account identifier (e.g., ACC-USER-001)
- **type**: CREDIT or DEBIT (case-insensitive)
- **amount**: Decimal number (e.g., 1500.00, 25.50)
- **currency**: ISO 4217 code (USD, EUR, GBP, JPY, AUD, CAD, etc.)
- **timestamp**: ISO 8601 format with timezone (e.g., 2026-09-01T10:00:00Z)

---

## 🚀 How to Upload (3 Methods)

### **Method 1: Using Swagger UI (Easiest)**

1. Open: http://localhost:8000/docs
2. Find the "POST /api/v1/imports" endpoint
3. Click "Try it out"
4. Click "Choose File" button
5. Select one of the sample CSV files:
   - `sample_transactions.csv`
   - `invoicing_batch.csv`
   - `daily_transactions.csv`
6. Click "Execute"
7. You'll get an import_id - copy it
8. Wait 2-3 seconds
9. Use GET endpoint to check status

### **Method 2: Using cURL Command**

```bash
# Set API key
API_KEY="RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

# Upload sample_transactions.csv
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@sample_transactions.csv"

# OR upload invoicing_batch.csv
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@invoicing_batch.csv"

# OR upload daily_transactions.csv
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@daily_transactions.csv"
```

### **Method 3: Using PowerShell**

```powershell
$apiKey = "RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"
$headers = @{"X-API-Key" = $apiKey}

# Using Invoke-RestMethod with file upload
$filePathcopy = "C:\Users\Tanvi Technology\Downloads\transaction-platform-master\transaction-platform-master\sample_transactions.csv"

$response = & curl.exe -X POST "http://localhost:8000/api/v1/imports" `
  -H "X-API-Key: $apiKey" `
  -F "file=@$filePath" 2>&1

$response | ConvertFrom-Json | ConvertTo-Json
```

---

## 📊 Example Upload Workflow

### Step 1: Upload CSV
```bash
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM" \
  -F "file=@sample_transactions.csv"
```

Response:
```json
{
  "import_id": "01M234ABCD1234567890ABCD",
  "status": "QUEUED"
}
```

### Step 2: Wait for Processing (2-3 seconds)
```bash
sleep 3
```

### Step 3: Check Import Status
```bash
curl -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM" \
  http://localhost:8000/api/v1/imports/01M234ABCD1234567890ABCD
```

Response:
```json
{
  "import_id": "01M234ABCD1234567890ABCD",
  "status": "COMPLETED",
  "total_rows": 8,
  "processed_rows": 8,
  "successful_rows": 8,
  "failed_rows": 0
}
```

### Step 4: View Transactions
```bash
curl -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM" \
  "http://localhost:8000/api/v1/transactions?limit=20"
```

Response: All 8 transactions from your CSV!

### Step 5: Check Account Balance
```bash
curl -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM" \
  http://localhost:8000/api/v1/accounts/ACC-USER-001/summary
```

Response:
```json
{
  "account_id": "ACC-USER-001",
  "total_credits": 2250.25,
  "total_debits": 250.50,
  "transaction_count": 3,
  "balance": 1999.75
}
```

---

## ✅ What Happens After Upload

1. **File is saved** to `/app/uploads/` with unique ID
2. **CSV header validated** - must have all required columns
3. **Import record created** in database with status QUEUED
4. **Message sent** to Redis queue
5. **Worker picks up** the job
6. **Worker streams CSV** - processes 1,000 rows at a time
7. **Each row validated**:
   - Check required fields present
   - Validate amount is positive number
   - Validate currency is valid ISO code
   - Validate timestamp format
8. **Transactions inserted** with duplicate prevention
9. **Account caches invalidated** in Redis
10. **Import status updated** to COMPLETED
11. **You can query results** immediately

---

## 🧪 Expected Results per File

### sample_transactions.csv
```
ACC-USER-001: $2,000 balance (3 transactions)
  - CREDIT: $1,500 + $750 = $2,250
  - DEBIT: $250.50
  - Balance: $1,999.50

ACC-USER-002: €4,200 balance (2 transactions)
  - CREDIT: €8,200
  - DEBIT: €4,000.75
  - Balance: €4,199.25

ACC-USER-003: £2,000 balance (2 transactions)
  - CREDIT: £2,500
  - DEBIT: £500
  - Balance: £2,000
```

### invoicing_batch.csv
```
ACC-INVOICING-01: $14,500 balance
ACC-INVOICING-02: €9,800 balance
ACC-INVOICING-03: £10,000 balance
```

### daily_transactions.csv
```
ACC-DAILY-A: $195 balance
ACC-DAILY-B: €280 balance
ACC-DAILY-C: £25 balance
```

---

## ❌ Common Upload Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| 400 Bad Request | File not CSV | Rename to .csv extension |
| 400 Missing columns | Header invalid | Check all required columns present |
| 401 Unauthorized | No API key | Add `-H "X-API-Key: ..."`  |
| 413 File too large | > 500MB | File is limited to 500MB |
| 202 but no data | Missing header row | Ensure CSV has proper header |

---

## 📝 Create Your Own CSV

Format template:
```csv
transaction_id,account_id,type,amount,currency,timestamp
YOUR-ID-001,YOUR-ACCOUNT-1,CREDIT,1000.00,USD,2026-09-09T10:00:00Z
YOUR-ID-002,YOUR-ACCOUNT-1,DEBIT,250.00,USD,2026-09-09T10:30:00Z
```

Rules:
- Each row is one transaction
- No blank rows
- All fields required
- Amount must be positive
- Currency must be valid ISO 4217
- Timestamp must be ISO 8601 format

---

## 🎯 Quick Start (Copy & Paste)

### Upload with Swagger (Easiest)
1. http://localhost:8000/docs
2. Find POST /api/v1/imports
3. Click "Choose File"
4. Select: `sample_transactions.csv`
5. Click Execute
6. Done! Data is processing

### Upload with cURL (Terminal)
```bash
API_KEY="RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@sample_transactions.csv" | jq
```

---

## 📍 File Locations

Sample files are in:
```
C:\Users\Tanvi Technology\Downloads\transaction-platform-master\transaction-platform-master\
```

Files:
- `sample_transactions.csv`
- `invoicing_batch.csv`
- `daily_transactions.csv`

Use these exact filenames in your upload commands.

---

## ✨ Next Steps

1. **Pick a file** from the 3 samples
2. **Upload it** using Swagger or cURL
3. **Check status** after 2-3 seconds
4. **Query results** with transactions endpoint
5. **View balance** with accounts endpoint

**That's it! Easy as that!** 🎉

---

Status: ✅ Ready to Upload
Sample Files: ✅ Created
API Key: ✅ Active
All Systems: ✅ Go
