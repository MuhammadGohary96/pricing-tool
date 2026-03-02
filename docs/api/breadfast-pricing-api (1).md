# Breadfast Product Pricing API

> **Base URL:** `https://catalog.breadfast.com`  
> **Authentication:** All requests require a `dashboard_jwt` cookie (set automatically in the browser) **or** an `Authorization: Bearer <token>` header for external tools like Postman.

---

## 1. Get Now Price & Now Sale Price for a Single Product ✅

> **Use this endpoint** — it matches exactly what the Breadfast dashboard uses and returns the correct, up-to-date pricing.

### Endpoint
```
GET https://catalog.breadfast.com/products/{productId}
```

### Query Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `select` | `id,name,nowPrice,nowSalePrice` | Only return the fields you need |

### Full Request URL
```
GET https://catalog.breadfast.com/products/2238325?select=id%2Cname%2CnowPrice%2CnowSalePrice
```

### Headers
```
Authorization: Bearer <dashboard_jwt>
```

### Example Response
```json
{
  "id": 2238325,
  "name": "Johnson's Sleep Time Baby Oil (200ml)",
  "nowPrice": 115,
  "nowSalePrice": 97.75
}
```

> **Note:** The response is a single object (not an array), since this endpoint returns one product directly by ID.

---

## ⚠️ Why Not the List Endpoint?

The list endpoint `GET /products?filter=id+eq+{id}` **can return stale or inconsistent pricing** and should **not** be used for fetching individual product prices. Always use the single product endpoint `GET /products/{productId}` for accurate pricing data.

| Endpoint | Result for product 2238325 | Accurate? |
|----------|---------------------------|-----------|
| `GET /products?filter=id+eq+2238325` | nowPrice: 103.5, nowSalePrice: 88 | ❌ Stale |
| `GET /products/2238325` | nowPrice: 115, nowSalePrice: 97.75 | ✅ Correct |

---

## 2. Get Prices for Multiple Products (List API)

Use the list endpoint only when fetching **multiple products** at once, not for individual price lookups.

### Endpoint
```
GET https://catalog.breadfast.com/products
```

### Query Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `select` | `id,name,nowPrice,nowSalePrice` | Only return the fields you need |
| `filter` | `isTrash eq false` | Exclude deleted products |
| `offset` | `0` | Pagination start index |
| `limit` | `10` | Number of results per page (max tested: 1000) |
| `orderby` | `id DESC` | Sort order |

### Full Request URL
```
GET https://catalog.breadfast.com/products?offset=0&limit=10&filter=isTrash+eq+false&select=id%2Cname%2CnowPrice%2CnowSalePrice&orderby=id+DESC
```

### Headers
```
Authorization: Bearer <dashboard_jwt>
```

### Example Response
```json
{
  "data": [
    {
      "id": 53411357,
      "name": "Molto Forni Plain Puff Pastry Sheets (10pcs)",
      "nowPrice": 50,
      "nowSalePrice": null
    },
    {
      "id": 53411207,
      "name": "Forni Puff Pastry Roll (430g)",
      "nowPrice": 45,
      "nowSalePrice": 40
    }
  ],
  "meta": {
    "offset": 0,
    "limit": 10,
    "count": 46481
  }
}
```

---

## 3. Update Now Price & Now Sale Price

### Endpoint
```
PATCH https://catalog.breadfast.com/products/{productId}
```

### Headers
```
Authorization: Bearer <dashboard_jwt>
Content-Type: application/json
```

### Request Body
```json
{
  "nowPrice": 120,
  "nowSalePrice": 99.99
}
```

> **Note:** Both fields are optional. Send only the field(s) you want to update.  
> Set `nowSalePrice` to `null` to remove an active sale price.

### Example — Update Product 2238325
```
PATCH https://catalog.breadfast.com/products/2238325
```
```json
{
  "nowPrice": 120,
  "nowSalePrice": 99.99
}
```

### Success Response — `200 OK`
Returns the full updated product object.

### Error Responses

| Status | Meaning |
|--------|---------|
| `401 Unauthorized` | Missing or expired JWT token |
| `403 Forbidden` | Insufficient permissions |
| `404 Not Found` | Product ID does not exist |
| `400 Bad Request` | Invalid field values |

---

## 4. Remove a Sale Price

To clear the sale price, set `nowSalePrice` to `null`:

```json
{
  "nowSalePrice": null
}
```

---

## 5. Postman Setup

### GET Single Product Price
1. Set method to **GET**
2. URL: `https://catalog.breadfast.com/products/2238325?select=id%2Cname%2CnowPrice%2CnowSalePrice`
3. Headers tab → add:
   ```
   Authorization: Bearer <dashboard_jwt>
   ```
4. Click **Send**

### PATCH Update Price
1. Set method to **PATCH**
2. URL: `https://catalog.breadfast.com/products/2238325`
3. Headers tab → add:
   ```
   Authorization: Bearer <dashboard_jwt>
   Content-Type: application/json
   ```
4. Body → raw → JSON:
   ```json
   {
     "nowPrice": 120,
     "nowSalePrice": 99.99
   }
   ```
5. Click **Send**

> **Getting the token:** Log into the Breadfast dashboard → DevTools → Application → Cookies → `www.breadfast.com` → copy the value of `dashboard_jwt`.

---

## 6. JavaScript / Fetch Examples

### Get Price for a Single Product ✅
```javascript
const JWT = 'your_dashboard_jwt_here';
const productId = 2238325;

const response = await fetch(
  `https://catalog.breadfast.com/products/${productId}?select=id%2Cname%2CnowPrice%2CnowSalePrice`,
  {
    headers: {
      'Authorization': `Bearer ${JWT}`
    }
  }
);

const product = await response.json();
console.log(`Product: ${product.name}`);
console.log(`Now Price: ${product.nowPrice}`);
console.log(`Now Sale Price: ${product.nowSalePrice ?? 'No active sale'}`);
```

### Get Prices for Multiple Products
```javascript
const JWT = 'your_dashboard_jwt_here';

const response = await fetch(
  'https://catalog.breadfast.com/products?offset=0&limit=100&filter=isTrash+eq+false&select=id%2Cname%2CnowPrice%2CnowSalePrice&orderby=id+DESC',
  {
    headers: {
      'Authorization': `Bearer ${JWT}`
    }
  }
);

const { data, meta } = await response.json();
console.log(`Total products: ${meta.count}`);
data.forEach(p => {
  console.log(`${p.id} | ${p.name} | Price: ${p.nowPrice} | Sale: ${p.nowSalePrice ?? 'N/A'}`);
});
```

### Update Price
```javascript
const JWT = 'your_dashboard_jwt_here';
const productId = 2238325;

const response = await fetch(
  `https://catalog.breadfast.com/products/${productId}`,
  {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${JWT}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      nowPrice: 120,
      nowSalePrice: 99.99
    })
  }
);

const updated = await response.json();
console.log('Updated:', updated);
```

---

## 7. Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `nowPrice` | `number` | Regular selling price for "Now" delivery |
| `nowSalePrice` | `number \| null` | Discounted sale price for "Now" delivery. `null` means no active sale |

---

*Generated from Breadfast Dashboard API — catalog.breadfast.com*  
*Last updated: corrected to use single product endpoint `GET /products/{id}` for accurate pricing*
