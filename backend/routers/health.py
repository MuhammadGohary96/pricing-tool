from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health_check(request: Request):
    svc = request.app.state.data_service
    df = svc.get_all_products()
    return {
        "status": "ok",
        "data_source": request.app.state.data_source,
        "product_count": len(df),
    }
