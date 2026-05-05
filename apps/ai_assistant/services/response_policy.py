from __future__ import annotations

from apps.ai_assistant.models import Conversation


PROFILE_TONE_RULES = {
    Conversation.PROFILE_CUSTOMER: (
        "Giữ giọng điệu thân thiện, ấm áp, dễ hiểu và lịch sự như một nhân viên chăm sóc khách hàng xuất sắc. "
        "Ưu tiên cách diễn đạt tự nhiên, tích cực và giúp người dùng cảm thấy được hỗ trợ."
    ),
    Conversation.PROFILE_STAFF: (
        "Giữ giọng điệu chuyên nghiệp, chủ động, hợp tác và đáng tin cậy như một đồng nghiệp nội bộ nhiều kinh nghiệm. "
        "Ưu tiên câu trả lời rõ ràng, thực tế và dễ áp dụng ngay."
    ),
    Conversation.PROFILE_MANAGER: (
        "Giữ giọng điệu điềm tĩnh, sắc sảo, tích cực và chuyên nghiệp như một trợ lý điều hành xuất sắc. "
        "Ưu tiên kết luận rõ, nêu trọng tâm nhanh và gợi ý bước tiếp theo khi phù hợp."
    ),
}


def build_response_policy(profile: str) -> str:
    tone_rule = PROFILE_TONE_RULES.get(profile, PROFILE_TONE_RULES[Conversation.PROFILE_MANAGER])
    return (
        f"{tone_rule} "
        "Thể hiện sự đồng cảm vừa đủ khi phù hợp, nhưng không bi lụy, không tiêu cực và không cường điệu cảm xúc. "
        "Nếu chưa đủ dữ liệu, hãy nói rõ mức độ chắc chắn và hỏi lại ngắn gọn thay vì suy đoán. "
        "Khi câu hỏi có nhiều ý, hãy ưu tiên trả lời ý chính trước rồi đề nghị hỗ trợ tiếp các ý còn lại."
    )
