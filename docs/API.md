# Payroll Management System API Documentation

This document provides comprehensive API documentation for the Payroll Management System.

## Base Information

- **Base URL**: `http://localhost:8000/api/payroll/`
- **API Version**: v1
- **Protocol**: HTTP/HTTPS
- **Authentication**: Django REST Framework Token or Session Authentication

## Authentication

### Token Authentication
```bash
# Get token
curl -X POST "http://localhost:8000/api-token-auth/" \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'

# Use token in requests
curl -X GET "http://localhost:8000/api/payroll/periods/" \
  -H "Authorization: Token your-token-here"
```

### Session Authentication
```bash
# Login via session
curl -X POST "http://localhost:8000/admin/login/" \
  -d "username=your_username&password=your_password" \
  -c cookies.txt

# Use session in requests
curl -X GET "http://localhost:8000/api/payroll/periods/" \
  -b cookies.txt
```

## Data Models

### PayrollPeriod Model

```json
{
  "id": "integer (read-only)",
  "start_date": "date (YYYY-MM-DD)",
  "end_date": "date (YYYY-MM-DD)", 
  "period_type": "choice (monthly|bi_weekly|weekly|custom)",
  "automation_enabled": "boolean",
  "automation_rule": "object (nullable)",
  "status": "choice (active|completed|cancelled)",
  "description": "string (nullable)",
  "meta": "object",
  "created_at": "datetime (read-only)",
  "updated_at": "datetime (read-only)",
  "is_active": "boolean (read-only)",
  "is_current": "boolean (read-only)",
  "duration_days": "integer (read-only)"
}
```

### Automation Rule Schema

```json
{
  "cron": "string (cron expression)",
  "days_before_end": "integer (0-30)",
  "run_on_date": "string (YYYY-MM-DD)",
  "notification_emails": ["array of email strings"]
}
```

## API Endpoints

### 1. List Payroll Periods

**GET** `/api/payroll/periods/`

List all payroll periods with optional filtering.

#### Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `status` | string | Filter by status | `active`, `completed`, `cancelled` |
| `period_type` | string | Filter by period type | `monthly`, `bi_weekly`, `weekly`, `custom` |
| `start_date` | date | Filter by start date (>=) | `2024-01-01` |
| `end_date` | date | Filter by end date (<=) | `2024-12-31` |
| `active_only` | boolean | Show only active periods | `true`, `false` |
| `page` | integer | Page number for pagination | `1`, `2`, `3` |

#### Response Schema

```json
{
  "count": "integer (total records)",
  "next": "string (next page URL or null)",
  "previous": "string (previous page URL or null)",
  "results": ["array of PayrollPeriod objects"]
}
```

#### Examples

**Request:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/?status=active&page=1" \
  -H "Authorization: Token your-token"
```

**Response:**
```json
{
  "count": 12,
  "next": "http://localhost:8000/api/payroll/periods/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "period_type": "monthly",
      "automation_enabled": true,
      "automation_rule": {
        "cron": "0 2 28 * *",
        "days_before_end": 3,
        "notification_emails": ["finance@company.com"]
      },
      "status": "active",
      "description": "January 2024 Payroll",
      "meta": {"fiscal_year": 2024, "quarter": "Q1"},
      "created_at": "2023-12-15T10:00:00Z",
      "updated_at": "2024-01-01T08:00:00Z",
      "is_active": true,
      "is_current": true,
      "duration_days": 31
    }
  ]
}
```

### 2. Create Payroll Period

**POST** `/api/payroll/periods/`

Create a new payroll period.

#### Request Body

```json
{
  "start_date": "2024-02-01",
  "end_date": "2024-02-29",
  "period_type": "monthly",
  "automation_enabled": true,
  "automation_rule": {
    "days_before_end": 5,
    "cron": "0 2 25 * *"
  },
  "status": "active",
  "description": "February 2024 Payroll"
}
```

#### Response

Returns the created PayrollPeriod object with HTTP 201 status.

#### Validation Rules

- `start_date` must be before `end_date`
- No overlapping periods of the same type
- `start_date` cannot be in the past for new periods
- `automation_rule` must have valid format if provided

#### Examples

**Request:**
```bash
curl -X POST "http://localhost:8000/api/payroll/periods/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{
    "start_date": "2024-02-01",
    "end_date": "2024-02-29", 
    "period_type": "monthly",
    "automation_enabled": true,
    "automation_rule": {
      "days_before_end": 5
    },
    "status": "active",
    "description": "February 2024 Payroll"
  }'
```

**Success Response (201):**
```json
{
  "id": 2,
  "start_date": "2024-02-01",
  "end_date": "2024-02-29",
  "period_type": "monthly",
  "automation_enabled": true,
  "automation_rule": {
    "days_before_end": 5
  },
  "status": "active",
  "description": "February 2024 Payroll",
  "meta": {},
  "created_at": "2024-01-15T14:30:00Z",
  "updated_at": "2024-01-15T14:30:00Z",
  "is_active": true,
  "is_current": false,
  "duration_days": 29
}
```

**Error Response (400):**
```json
{
  "end_date": ["End date must be after start date."],
  "start_date": ["This period overlaps with existing Monthly period (2024-01-15 to 2024-02-15)."]
}
```

### 3. Retrieve Payroll Period

**GET** `/api/payroll/periods/{id}/`

Get details of a specific payroll period.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | PayrollPeriod ID |

#### Response

Returns PayrollPeriod object with HTTP 200 status.

#### Examples

**Request:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/1/" \
  -H "Authorization: Token your-token"
```

**Success Response (200):**
```json
{
  "id": 1,
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "period_type": "monthly",
  "automation_enabled": true,
  "automation_rule": {
    "cron": "0 2 28 * *",
    "days_before_end": 3
  },
  "status": "active",
  "description": "January 2024 Payroll",
  "meta": {},
  "created_at": "2023-12-15T10:00:00Z",
  "updated_at": "2024-01-01T08:00:00Z",
  "is_active": true,
  "is_current": true,
  "duration_days": 31
}
```

**Error Response (404):**
```json
{
  "detail": "Not found."
}
```

### 4. Update Payroll Period

**PUT** `/api/payroll/periods/{id}/`

Update an existing payroll period (full update).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | PayrollPeriod ID |

#### Request Body

Complete PayrollPeriod object (same as create).

#### Response

Returns updated PayrollPeriod object with HTTP 200 status.

### 5. Partial Update Payroll Period

**PATCH** `/api/payroll/periods/{id}/`

Partially update a payroll period.

#### Examples

**Request:**
```bash
curl -X PATCH "http://localhost:8000/api/payroll/periods/1/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{"description": "Updated January 2024 Payroll"}'
```

### 6. Delete Payroll Period

**DELETE** `/api/payroll/periods/{id}/`

Delete a payroll period. Only periods with status != 'completed' can be deleted.

#### Response

Returns HTTP 204 No Content on success.

#### Examples

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/payroll/periods/1/" \
  -H "Authorization: Token your-token"
```

**Error Response (400) - Cannot delete completed period:**
```json
{
  "non_field_errors": ["Cannot delete a completed payroll period. Consider cancelling it instead."]
}
```

### 7. Export Periods to CSV

**GET** `/api/payroll/periods/export-csv/`

Export payroll periods to CSV format.

#### Query Parameters

Same filtering parameters as list endpoint.

#### Response

CSV file download with HTTP 200 status.

#### Examples

**Request:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/export-csv/?status=active" \
  -H "Authorization: Token your-token" \
  -o payroll_periods.csv
```

**CSV Format:**
```csv
ID,Start Date,End Date,Period Type,Status,Automation Enabled,Automation Rule,Description,Created At,Updated At,Duration Days,Is Active,Is Current
1,2024-01-01,2024-01-31,Monthly,Active,Yes,"{""days_before_end"": 3}",January 2024 Payroll,2023-12-15 10:00:00,2024-01-01 08:00:00,31,Yes,Yes
```

### 8. Import Periods from CSV

**POST** `/api/payroll/periods/import-csv/`

Import payroll periods from CSV file.

#### Request Body

Multipart form data with file upload.

#### Form Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | file | CSV file to import |

#### CSV Format Required

```csv
Start Date,End Date,Period Type,Status,Automation Enabled,Description
2024-03-01,2024-03-31,monthly,active,Yes,March 2024 Payroll
2024-04-01,2024-04-30,monthly,active,No,April 2024 Payroll
```

#### Response

```json
{
  "message": "Import completed. Created: 2, Updated: 0",
  "created_count": 2,
  "updated_count": 0, 
  "error_count": 0,
  "errors": []
}
```

#### Examples

**Request:**
```bash
curl -X POST "http://localhost:8000/api/payroll/periods/import-csv/" \
  -H "Authorization: Token your-token" \
  -F "file=@payroll_periods.csv"
```

### 9. Get Period Summary

**GET** `/api/payroll/periods/{id}/summary/`

Get aggregated summary data for a payroll period.

#### Response Schema

```json
{
  "id": "integer",
  "start_date": "date",
  "end_date": "date",
  "period_type": "string",
  "status": "string", 
  "description": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "is_active": "boolean",
  "is_current": "boolean",
  "duration_days": "integer",
  "total_employees": "integer",
  "total_gross_pay": "decimal", 
  "total_deductions": "decimal",
  "total_net_pay": "decimal",
  "average_gross_pay": "decimal"
}
```

#### Examples

**Request:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/1/summary/" \
  -H "Authorization: Token your-token"
```

**Response:**
```json
{
  "id": 1,
  "start_date": "2024-01-01",
  "end_date": "2024-01-31", 
  "period_type": "monthly",
  "status": "active",
  "description": "January 2024 Payroll",
  "created_at": "2023-12-15T10:00:00Z",
  "updated_at": "2024-01-01T08:00:00Z",
  "is_active": true,
  "is_current": true,
  "duration_days": 31,
  "total_employees": 150,
  "total_gross_pay": "750000.00",
  "total_deductions": "150000.00", 
  "total_net_pay": "600000.00",
  "average_gross_pay": "5000.00"
}
```

### 10. Trigger Payroll Run

**POST** `/api/payroll/periods/{id}/run/`

Trigger payroll processing for a specific period.

#### Request Body Schema

```json
{
  "run_type": "choice (full|preview|test)",
  "include_bonuses": "boolean",
  "include_overtime": "boolean", 
  "notification_emails": ["array of email strings"],
  "notes": "string"
}
```

#### Response Schema

```json
{
  "success": "boolean",
  "message": "string",
  "period_id": "integer",
  "timestamp": "datetime",
  "run_parameters": "object",
  "period": "object",
  "results": "object"
}
```

#### Examples

**Request:**
```bash
curl -X POST "http://localhost:8000/api/payroll/periods/1/run/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{
    "run_type": "full",
    "include_bonuses": true,
    "include_overtime": true,
    "notification_emails": ["hr@company.com", "finance@company.com"],
    "notes": "Regular monthly payroll run"
  }'
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Payroll processing completed successfully",
  "period_id": 1,
  "timestamp": "2024-01-15T16:30:00Z",
  "run_parameters": {
    "run_type": "full",
    "include_bonuses": true,
    "include_overtime": true,
    "notification_emails": ["hr@company.com", "finance@company.com"],
    "notes": "Regular monthly payroll run"
  },
  "period": {
    "id": 1,
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "period_type": "Monthly"
  },
  "results": {
    "employees_processed": 150,
    "total_amount": "600000.00",
    "processing_time": "45.2 seconds"
  }
}
```

**Error Response (422) - Processing Failed:**
```json
{
  "error": "Payroll processing failed",
  "details": "Period is not in active status",
  "period_id": 1
}
```

**Error Response (400) - Validation Failed:**
```json
{
  "error": "Invalid payroll run parameters",
  "details": {
    "period_id": ["Payroll period with ID 999 does not exist."],
    "run_type": ["\"invalid\" is not a valid choice."]
  }
}
```

## Error Handling

### HTTP Status Codes

| Code | Description | Usage |
|------|-------------|-------|
| 200 | OK | Successful GET, PUT, PATCH requests |
| 201 | Created | Successful POST requests |
| 204 | No Content | Successful DELETE requests |
| 400 | Bad Request | Validation errors, malformed requests |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Permission denied |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Business logic errors |
| 500 | Internal Server Error | Server errors |

### Error Response Format

All error responses follow a consistent format:

```json
{
  "error": "Error type or message",
  "details": "Detailed error description or validation errors object"
}
```

### Common Validation Errors

**Field-specific errors:**
```json
{
  "start_date": ["This field is required."],
  "end_date": ["End date must be after start date."],
  "period_type": ["\"invalid\" is not a valid choice."]
}
```

**Non-field errors:**
```json
{
  "non_field_errors": ["Cannot delete a completed payroll period."]
}
```

## Permissions and Access Control

### Permission Classes

1. **PayrollPeriodPermissions**: Controls CRUD operations based on user roles
2. **CanRunPayroll**: Required for triggering payroll runs
3. **CanViewAllPeriods**: Required for viewing summaries and all periods
4. **IsFinanceOrAdmin**: Finance/Admin only operations

### Role-Based Access

| Operation | Finance | Admin | HR | Regular User |
|-----------|---------|-------|----|----|
| List periods | ✅ | ✅ | ✅ | Limited |
| Create period | ✅ | ✅ | ❌ | ❌ |
| Update period | ✅ | ✅ | ❌ | ❌ |
| Delete period | ✅ | ✅ | ❌ | ❌ |
| View summary | ✅ | ✅ | ✅ | ❌ |
| Run payroll | ✅ | ✅ | ✅ | ❌ |
| Export CSV | ✅ | ✅ | ❌ | ❌ |
| Import CSV | ✅ | ✅ | ❌ | ❌ |

## Rate Limiting

API endpoints may be rate-limited in production:

- Default: 100 requests per minute per user
- Payroll run endpoint: 5 requests per minute per user
- CSV operations: 10 requests per minute per user

## Pagination

List endpoints use page-based pagination:

- Default page size: 50 items
- Maximum page size: 100 items
- Use `page` query parameter for navigation

Example pagination response:
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/payroll/periods/?page=2",
  "previous": null,
  "results": [...]
}
```

## Field Filtering and Ordering

### Available Filters

- `status` - Filter by period status
- `period_type` - Filter by period type
- `start_date` - Filter by start date (>=)
- `end_date` - Filter by end date (<=) 
- `active_only` - Show only active periods

### Ordering

Use `ordering` query parameter:

```bash
# Order by start date (ascending)
GET /api/payroll/periods/?ordering=start_date

# Order by start date (descending) 
GET /api/payroll/periods/?ordering=-start_date

# Multiple fields
GET /api/payroll/periods/?ordering=-created_at,start_date
```

Available ordering fields:
- `start_date`
- `end_date` 
- `created_at`
- `updated_at`
- `period_type`
- `status`

## API Versioning

Currently using v1 implicit versioning. Future versions will use explicit versioning:

```bash
GET /api/v2/payroll/periods/
```

## Client Libraries

### Python Example

```python
import requests

class PayrollClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"Authorization": f"Token {token}"}
    
    def list_periods(self, **filters):
        response = requests.get(
            f"{self.base_url}/periods/",
            headers=self.headers,
            params=filters
        )
        return response.json()
    
    def create_period(self, period_data):
        response = requests.post(
            f"{self.base_url}/periods/",
            headers=self.headers,
            json=period_data
        )
        return response.json()
    
    def run_payroll(self, period_id, run_params=None):
        response = requests.post(
            f"{self.base_url}/periods/{period_id}/run/",
            headers=self.headers, 
            json=run_params or {}
        )
        return response.json()

# Usage
client = PayrollClient("http://localhost:8000/api/payroll", "your-token")
periods = client.list_periods(status="active")
```

### JavaScript Example

```javascript
class PayrollAPI {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
        };
    }

    async listPeriods(filters = {}) {
        const params = new URLSearchParams(filters);
        const response = await fetch(
            `${this.baseUrl}/periods/?${params}`,
            { headers: this.headers }
        );
        return response.json();
    }

    async createPeriod(periodData) {
        const response = await fetch(
            `${this.baseUrl}/periods/`,
            {
                method: 'POST',
                headers: this.headers,
                body: JSON.stringify(periodData)
            }
        );
        return response.json();
    }

    async runPayroll(periodId, runParams = {}) {
        const response = await fetch(
            `${this.baseUrl}/periods/${periodId}/run/`,
            {
                method: 'POST', 
                headers: this.headers,
                body: JSON.stringify(runParams)
            }
        );
        return response.json();
    }
}

// Usage
const api = new PayrollAPI('http://localhost:8000/api/payroll', 'your-token');
const periods = await api.listPeriods({ status: 'active' });
```

## Testing

### Test Endpoints

Use Django's test client or tools like Postman:

```python
from rest_framework.test import APITestCase
from django.contrib.auth.models import User

class PayrollAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('test', 'test@example.com', 'pass')
        self.client.force_authenticate(user=self.user)
    
    def test_list_periods(self):
        response = self.client.get('/api/payroll/periods/')
        self.assertEqual(response.status_code, 200)
```

## Changelog

### v1.0.0 (Current)
- Initial API release
- Basic CRUD operations for payroll periods
- CSV import/export functionality
- Payroll run triggering
- Period summary aggregations
- Role-based permissions

### Future Versions
- v1.1.0: Advanced filtering and search
- v1.2.0: Bulk operations support
- v2.0.0: GraphQL support
