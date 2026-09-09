# Complete API Testing Guide

All endpoints have been verified and are working correctly.

## 🔑 Your Test API Key

```
X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM
```

Keep this key for testing all endpoints.

---

## 📚 API ENDPOINTS - COMPLETE REFERENCE

### 1. HEALTH ENDPOINTS

#### 1.1 Liveness Check (No Auth Required)
```bash
curl http://localhost:8000/health/live

Response: {"status":"ok"}
Status Code: 200
```

#### 1.2 Readiness Check (No Auth Required)
```bash
curl http://localhost:8000/health/ready

Response: {"status":"ready","postgresql":"ok","redis":"ok"}
Status Code: 200
```

---

### 2. IMPORT ENDPOINTS

#### 2.1 Upload CSV File
```bash
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM" \
  -F "file=@transactions.csv"

Request Body:
- file: multipart/form-data (CSV file)

Response: {
  "import_id": "01M233NZ983CTSQRV3TP233QMR",
  "status": "QUEUED"
}
Status Code: 202 (Accepted)
```

**CSV Format Required:**
```csv
transaction_id,account_id,type,amount,currency,timestamp
TXN-001,ACC-1001,CREDIT,1500.00,USD,2026-09-01T10:00:00Z
TXN-002,ACC-1001,DEBIT,250.00,USD,2026-09-01T10:01:00Z
```

#### 2.2 Get Import Status
```bash
curl http://localhost:8000/api/v1/imports/01M233NZ983CTSQRV3TP233QMR \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

Response: {
  "import_id": "01M233NZ983CTSQRV3TP233QMR",
  "status": "COMPLETED",
  "total_rows": 2,
  "processed_rows": 2,
  "successful_rows": 2,
  "failed_rows": 0,
  "started_at": "2026-09-09T12:53:25.123456Z",
  "completed_at": "2026-09-09T12:53:26.789012Z",
  "error_message": null
}
Status Code: 200
```

Possible statuses:
- `QUEUED` - Waiting to be processed
- `PROCESSING` - Currently being processed
- `COMPLETED` - Successfully completed
- `FAILED` - Failed with error

#### 2.3 Get Import Errors (Paginated)
```bash
curl "http://localhost:8000/api/v1/imports/01M233NZ983CTSQRV3TP233QMR/errors?page=1&limit=50" \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

Query Parameters:
- page: int (default 1, min 1)
- limit: int (default 50, min 1, max 500)

Response: {
  "items": [
    {
      "row": 5,
      "transaction_id": "TXN-005",
      "error": "amount is not a valid number: 'invalid'"
    }
  ],
  "page": 1,
  "limit": 50,
  "total": 1
}
Status Code: 200
```

---

### 3. TRANSACTION ENDPOINTS

#### 3.1 List Transactions (With Filters & Pagination)
```bash
curl "http://localhost:8000/api/v1/transactions?page=1&limit=50&account_id=ACC-1001&sort_by=timestamp&sort_order=desc" \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

Query Parameters:
- page: int (default 1, min 1)
- limit: int (default 50, min 1, max 500)
- account_id: string (optional filter)
- type: string (optional: CREDIT or DEBIT)
- currency: string (optional: ISO 4217 code, e.g., USD, EUR)
- date_from: ISO 8601 datetime (optional, inclusive)
- date_to: ISO 8601 datetime (optional, inclusive)
- sort_by: string (default timestamp, options: timestamp, amount, transaction_id, created_at)
- sort_order: string (default desc, options: asc, desc)

Response: {
  "items": [
    {
      "id": "6d63e16e-07da-4fcb-a6cf-b61c1977210d",
      "transaction_id": "TXN-004",
      "account_id": "ACC-1002",
      "type": "DEBIT",
      "amount": "1000.00000000",
      "currency": "EUR",
      "timestamp": "2026-09-01T11:30:00Z",
      "import_id": "01M233NZ983CTSQRV3TP233QMR",
      "created_at": "2026-09-09T12:53:28.190328Z"
    }
  ],
  "page": 1,
  "limit": 50,
  "total": 4
}
Status Code: 200
```

#### 3.2 Get Single Transaction
```bash
curl http://localhost:8000/api/v1/transactions/TXN-001 \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

Response: {
  "id": "55a801ba-453c-4e37-9ab5-e8d12400cd69",
  "transaction_id": "TXN-001",
  "account_id": "ACC-1001",
  "type": "CREDIT",
  "amount": "1500.00000000",
  "currency": "USD",
  "timestamp": "2026-09-01T10:00:00Z",
  "import_id": "01M233NZ983CTSQRV3TP233QMR",
  "created_at": "2026-09-09T12:53:28.190328Z"
}
Status Code: 200
```

---

### 4. ACCOUNT ENDPOINTS

#### 4.1 Get Account Summary (Balance & Totals)
```bash
curl http://localhost:8000/api/v1/accounts/ACC-1001/summary \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

Response: {
  "account_id": "ACC-1001",
  "total_credits": 1500.0,
  "total_debits": 250.0,
  "transaction_count": 2,
  "balance": 1250.0
}
Status Code: 200

Notes:
- Balance = total_credits - total_debits
- Cached for 300 seconds (auto-invalidated after import)
```

---

### 5. DOCUMENTATION ENDPOINTS

#### 5.1 Swagger UI (Interactive Testing)
```
http://localhost:8000/docs
```

#### 5.2 ReDoc (Read-only Documentation)
```
http://localhost:8000/redoc
```

---

## 🧪 TEST SCENARIOS

### Scenario 1: Upload and Process CSV

```bash
# Step 1: Create test CSV
cat > test.csv << 'EOF'
transaction_id,account_id,type,amount,currency,timestamp
TXN-TEST-001,ACC-9999,CREDIT,1000.00,USD,2026-09-01T10:00:00Z
TXN-TEST-002,ACC-9999,DEBIT,250.00,USD,2026-09-01T11:00:00Z
EOF

# Step 2: Upload CSV
API_KEY="RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"
IMPORT_ID=$(curl -s -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@test.csv" | jq -r '.import_id')

echo "Import ID: $IMPORT_ID"

# Step 3: Wait for processing
sleep 3

# Step 4: Check import status
curl -s http://localhost:8000/api/v1/imports/$IMPORT_ID \
  -H "X-API-Key: $API_KEY" | jq

# Step 5: Get transactions
curl -s "http://localhost:8000/api/v1/transactions?account_id=ACC-9999" \
  -H "X-API-Key: $API_KEY" | jq

# Step 6: Get account summary
curl -s http://localhost:8000/api/v1/accounts/ACC-9999/summary \
  -H "X-API-Key: $API_KEY" | jq
```

### Scenario 2: Test Rate Limiting

```bash
API_KEY="RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

# Send 101 requests rapidly (limit is 100 per 60 seconds)
for i in {1..101}; do
  curl -s http://localhost:8000/api/v1/transactions \
    -H "X-API-Key: $API_KEY" > /dev/null
  echo "Request $i"
done

# The 101st request should return 429 Too Many Requests
```

### Scenario 3: Test CSV Validation Errors

```bash
# Create invalid CSV
cat > invalid.csv << 'EOF'
transaction_id,account_id,type,amount,currency,timestamp
TXN-INVALID-001,ACC-1001,INVALID_TYPE,abc,INVALID_CURRENCY,not-a-date
EOF

API_KEY="RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

# Upload and check for errors
IMPORT_ID=$(curl -s -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@invalid.csv" | jq -r '.import_id')

sleep 2

# Get errors
curl -s http://localhost:8000/api/v1/imports/$IMPORT_ID/errors \
  -H "X-API-Key: $API_KEY" | jq '.items'
```

### Scenario 4: Test Authentication

```bash
# Without API key - should return 401
curl -s http://localhost:8000/api/v1/transactions

# With invalid API key - should return 401
curl -s http://localhost:8000/api/v1/transactions \
  -H "X-API-Key: invalid_key_123"

# With valid API key - should return 200
curl -s http://localhost:8000/api/v1/transactions \
  -H "X-API-Key: RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"
```

---

## 🔍 ERROR HANDLING

### Common Errors

| Status | Error | Cause | Solution |
|--------|-------|-------|----------|
| 400 | Missing required columns | CSV header invalid | Check CSV header matches schema |
| 400 | amount is not a valid number | Invalid decimal format | Use valid numbers like "1500.00" |
| 400 | currency is not a valid ISO 4217 code | Invalid currency | Use valid codes like USD, EUR, GBP |
| 401 | X-API-Key header required | No API key provided | Add `-H "X-API-Key: ..."` to request |
| 401 | Invalid or inactive API key | Wrong/inactive key | Check key value, recreate if needed |
| 404 | Import not found | Invalid import ID | Check import ID spelling |
| 404 | Transaction not found | Invalid transaction ID | Check transaction_id exists |
| 404 | Account not found | No transactions for account | Create transactions first |
| 413 | File exceeds limit | CSV too large | Max size is 500 MB |
| 429 | Too Many Requests | Rate limit exceeded | Wait 60 seconds, max 100 req/min |
| 503 | Service Unavailable | Database/Redis down | Check docker compose status |

---

## 📊 INTERACTIVE TESTING

### Using Swagger UI

1. Open: `http://localhost:8000/docs`
2. Click "Authorize" button (top right)
3. Enter API Key: `RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM`
4. Click each endpoint to expand and test
5. Click "Try it out" button
6. Modify parameters as needed
7. Click "Execute"
8. View response

---

## 📝 CURL COMMAND REFERENCE

```bash
# Set API key as variable
API_KEY="RMSeFMzNOT4Iy3SAM3NDda2iX1s4u_kzbwXDhFUmYtM"

# GET request (with auth)
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/transactions

# POST with file upload
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@transactions.csv"

# Query parameters
curl "http://localhost:8000/api/v1/transactions?page=2&limit=25" \
  -H "X-API-Key: $API_KEY"

# Pretty print JSON
curl -s http://localhost:8000/api/v1/transactions \
  -H "X-API-Key: $API_KEY" | jq .

# Save response to file
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/transactions \
  > response.json

# Pipe to file
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@test.csv" | jq . | tee upload_response.json
```

---

## ✅ VERIFICATION CHECKLIST

All items below have been tested and verified working:

- [x] Health endpoints return correct status
- [x] CSV upload endpoint accepts valid files
- [x] Import status tracking works
- [x] Transactions are stored correctly
- [x] Account summary calculations correct
- [x] Rate limiting works (100 req/60s)
- [x] Caching invalidates on import
- [x] Error handling returns proper status codes
- [x] Pagination works correctly
- [x] Filtering by account/type/currency works
- [x] Sorting works for all fields
- [x] Authentication required for all API endpoints
- [x] Worker processes CSV asynchronously
- [x] Duplicate prevention works
- [x] Documentation endpoints accessible

---

## 🎯 SUCCESS CRITERIA MET

✅ All 7 API endpoints working
✅ Authentication implemented
✅ Rate limiting functional
✅ Caching operational
✅ Worker processing jobs
✅ Error handling robust
✅ Documentation complete
✅ Database operations verified
✅ Redis integration working
✅ Async processing confirmed

---

**Status**: Production Ready (Local Testing)  
**Last Verified**: 2026-09-09 12:53:00 UTC  
**All Tests**: ✅ PASSING
