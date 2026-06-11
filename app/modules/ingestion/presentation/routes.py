from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.response import StandardResponse, create_success_response
from app.core.settings import get_settings
from app.modules.ingestion.domain.usecases.ingest_email import IngestEmailUseCase
from app.modules.ingestion.presentation.schemas import IngestEmailRequest, IngestEmailResponse

router = APIRouter(prefix="/ingest", tags=["ingestion"])


def verify_webhook_token(x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token")) -> None:
    if x_webhook_token != get_settings().webhook_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token")


@router.post("/email", response_model=StandardResponse[IngestEmailResponse], dependencies=[Depends(verify_webhook_token)])
async def ingest_email(
    payload: IngestEmailRequest,
    request: Request,
) -> StandardResponse[IngestEmailResponse]:
    usecase: IngestEmailUseCase = request.app.state.ingest_usecase
    mention = await usecase.execute(payload.to_domain())
    return create_success_response(IngestEmailResponse(_id=mention.id, status=mention.status.value))
