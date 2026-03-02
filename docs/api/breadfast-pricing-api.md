# Breadfast Product Pricing API

> **Base URL:** `https://catalog.breadfast.com`  
> **Authentication:** All requests require a `dashboard_jwt` cookie (set automatically in the browser) **or** an `Authorization: Bearer <token>` header for external tools like Postman.

---

## 1. Get Now Price & Now Sale Price

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

## 2. Get Price for a Single Product

### Endpoint
```
GET https://catalog.breadfast.com/products?filter=id+eq+{productId}%2C+isTrash+eq+false&select=id%2Cname%2CnowPrice%2CnowSalePrice
```

### Example — Product ID 52766064
```
GET https://catalog.breadfast.com/products?filter=id+eq+52766064%2C+isTrash+eq+false&select=id%2Cname%2CnowPrice%2CnowSalePrice
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
      "id": 52766064,
      "name": "Juhayna Greek Yogurt Strawberry Hibiscus Chia Seeds Single Pack (180g)",
      "nowPrice": 50,
      "nowSalePrice": null
    }
  ],
  "meta": {
    "offset": 0,
    "limit": 10,
    "count": 1
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
  "nowPrice": 55,
  "nowSalePrice": 49.99
}
```

> **Note:** Both fields are optional. Send only the field(s) you want to update.  
> Set `nowSalePrice` to `null` to remove a sale price.

### Example — Update Product 52766064
```
PATCH https://catalog.breadfast.com/products/52766064
```
```json
{
  "nowPrice": 55,
  "nowSalePrice": 49.99
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

1. Create a new **GET** or **PATCH** request with the URL above.
2. Go to the **Headers** tab and add:
   ```
   Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
   Content-Type: application/json
   ```
3. For PATCH, go to **Body → raw → JSON** and enter the fields to update.
4. Click **Send**.

> **Getting the token:** Log into the Breadfast dashboard, open DevTools → Application → Cookies → `www.breadfast.com` → copy the value of `dashboard_jwt`.

---

## 6. JavaScript / Fetch Example

### Get Prices
```javascript
const JWT = 'your_dashboard_jwt_here';

const response = await fetch(
  'https://catalog.breadfast.com/products?offset=0&limit=10&filter=isTrash+eq+false&select=id%2Cname%2CnowPrice%2CnowSalePrice&orderby=id+DESC',
  {
    headers: {
      'Authorization': `Bearer ${JWT}`
    }
  }
);

const { data, meta } = await response.json();
console.log(`Total products: ${meta.count}`);
data.forEach(p => console.log(`${p.id} | ${p.name} | Price: ${p.nowPrice} | Sale: ${p.nowSalePrice ?? 'N/A'}`));
```

### Update Price
```javascript
const JWT = 'your_dashboard_jwt_here';
const productId = 52766064;

const response = await fetch(
  `https://catalog.breadfast.com/products/${productId}`,
  {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${JWT}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      nowPrice: 55,
      nowSalePrice: 49.99
    })
  }
);

const updated = await response.json();
console.log('Updated product:', updated);
```

---

## 7. Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `nowPrice` | `number` | Regular selling price for "Now" delivery |
| `nowSalePrice` | `number \| null` | Discounted sale price for "Now" delivery. `null` means no active sale |

---

*Generated from Breadfast Dashboard API — catalog.breadfast.com*
