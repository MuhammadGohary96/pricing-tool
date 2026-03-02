"""
Breadfast Catalog API client.

Fetches live nowPrice and nowSalePrice from catalog.breadfast.com.

IMPORTANT: The list endpoint (GET /products?filter=...) returns STALE prices.
The single product endpoint (GET /products/{id}) returns CORRECT prices.
We use the single endpoint with concurrent requests for accuracy.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import httpx

# Shared lock for thread-safe progress printing
_print_lock = Lock()


def fetch_prices_by_ids(
    base_url: str,
    token: str,
    product_ids: list[int],
    max_workers: int = 20,
    progress_status: dict = None,
) -> dict[int, dict]:
    """
    Fetch accurate prices for specific product IDs using GET /products/{id}.

    Uses a shared httpx.Client with connection pooling for efficiency.

    Returns: {product_id: {"now_price": float|None, "now_sale_price": float|None}}
    """
    if not token:
        print("[Catalog] No BF_CATALOG_TOKEN set — skipping live price fetch")
        return {}

    if not product_ids:
        return {}

    total = len(product_ids)
    print(f"[Catalog] Fetching accurate prices for {total} products...", flush=True)

    if progress_status is not None:
        progress_status["total"] = total
        progress_status["progress"] = 0

    result: dict[int, dict] = {}
    errors = 0
    done = 0
    headers = {"Authorization": f"Bearer {token}"}

    # Use a single shared client with connection pooling
    with httpx.Client(
        timeout=15.0,
        limits=httpx.Limits(max_connections=max_workers, max_keepalive_connections=max_workers),
    ) as client:

        def _fetch_one(pid: int) -> tuple[int, dict | None]:
            url = f"{base_url}/{pid}"
            try:
                resp = client.get(url, params={"select": "id,nowPrice,nowSalePrice"}, headers=headers)
                if resp.status_code == 404:
                    return (pid, None)
                resp.raise_for_status()
                item = resp.json()
                return (pid, {
                    "now_price": item.get("nowPrice"),
                    "now_sale_price": item.get("nowSalePrice"),
                })
            except Exception:
                return (pid, None)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_one, pid): pid for pid in product_ids}

            for future in as_completed(futures):
                pid, data = future.result()
                if data is not None:
                    result[pid] = data
                else:
                    errors += 1
                done += 1
                if progress_status is not None:
                    progress_status["progress"] = done
                if done % 500 == 0 or done == total:
                    with _print_lock:
                        print(f"[Catalog] Fetched {done}/{total} ({errors} errors)...", flush=True)
                        sys.stdout.flush()

    print(f"[Catalog] Done — got accurate prices for {len(result)} of {total} products", flush=True)
    return result


def update_product_price(
    base_url: str,
    token: str,
    product_id: int,
    now_price: float | None = None,
    now_sale_price: float | None = None,
) -> dict:
    """
    PATCH a single product's nowPrice / nowSalePrice on the Catalog API.

    Returns the API response body on success, raises on error.
    """
    url = f"{base_url}/{product_id}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body = {}
    if now_price is not None:
        body["nowPrice"] = now_price
    if now_sale_price is not None:
        body["nowSalePrice"] = now_sale_price

    with httpx.Client(timeout=15.0) as client:
        resp = client.patch(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()
