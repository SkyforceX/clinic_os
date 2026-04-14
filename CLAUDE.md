# CLAUDE.md

## Context
clinic_os là Django monolith đang refactor (legacy + domain cùng tồn tại)

## Nguyên tắc
- Không phá template path, JS path, URL
- Sửa nhỏ, không refactor lớn
- Luôn đọc code hiện tại trước khi sửa

## Kiến trúc
- models / selectors / services / policies / web / api
- follow pattern của app đang sửa

## Quy tắc quan trọng
- contract / quotation → dùng snapshot, không phụ thuộc source
- giữ nguyên UI, không redesign
- không đổi logic role

## Output yêu cầu
- root cause
- file cần sửa
- code copy-paste được