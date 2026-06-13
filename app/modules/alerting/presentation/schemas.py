from pydantic import BaseModel


class ManualAlertRequest(BaseModel):
    cluster_id: int
