from pydantic import BaseModel

from app.modules.generation.domain.models import ArtifactType


class GenerateRequest(BaseModel):
    type: ArtifactType
    variant: str | None = None  # dành cho mở rộng; brand_voice tự sinh nhiều variant
    # Yêu cầu tự do người dùng gõ kèm (vd "viết ngắn", "tập trung nguyên nhân") —
    # ưu tiên tuyệt đối khi sinh, ghi đè quy ước hình thức mặc định của playbook.
    instruction: str = ""


class ChatGenerateRequest(BaseModel):
    """Sinh nội dung từ chat (3 skill content/design_brief/response_plan).

    `context` là ngữ cảnh tự do (artifact đã inject / lịch sử hội thoại). Khi có
    `cluster_id`, RT1 dựng thêm ClusterContext và chèn vào ngữ cảnh. `instruction` là
    yêu cầu cụ thể người dùng gõ kèm khi chọn skill (ưu tiên tuyệt đối khi sinh).
    """

    type: ArtifactType
    context: str = ""
    instruction: str = ""
    cluster_id: int | None = None
    session_id: str | None = None
