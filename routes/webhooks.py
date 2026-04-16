from routes.retry import router
from fastapi import APIRouter, Request


@router.post("/webhooks/eopyy")
async def receive_webhook(request: Request):
    payload = await request.json()
    print(payload)
    return {"status": "ok"}
