import os
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.utils.text import slugify
import pandas as pd
import openpyxl
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from datetime import datetime
import re
import pickle

#*****  openpyxl giữ đúng định dạng excel ban đầu


# Đọc file pkl
sum = Path(r"D:/Code/Project\Django project/VMD/unicore/media/temp/sum.xlsx")
ranged_list = Path(r"D:/Code/Project\Django project/VMD/unicore/media/temp/sum_final.xlsx")



# # 1. Đọc dữ liệu từ file xét nghiệm test.xlsx
# df_blood = pd.read_excel(test)

# # Chuẩn hóa tên cột (nếu cần)
# df_blood.columns = [col.strip() for col in df_blood.columns]
# # Đổi tên cho khớp dễ merge (nếu cần)
# df_blood = df_blood.rename(columns={
#     'Họ tên': 'Họ tên',
#     'Giới tính': 'Giới tính',
#     'Năm sinh': 'Năm sinh',
#     'Yêu cầu': 'Yêu cầu',
#     'Kết quả': 'Kết quả'
# })

# # 2. Lọc các dịch vụ liên quan nhóm máu
# df_blood['Yêu cầu lower'] = df_blood['Yêu cầu'].str.lower()
# mask = df_blood['Yêu cầu lower'].str.contains('nhóm máu|rhesus')
# df_blood_filtered = df_blood[mask].copy()

# # Pivot thành từng người, mỗi dịch vụ 1 cột
# pivoted = df_blood_filtered.pivot_table(
#     index=['Họ tên', 'Giới tính', 'Năm sinh'],
#     columns='Yêu cầu lower',
#     values='Kết quả',
#     aggfunc='first'
# ).reset_index()

# # Gộp nhóm máu và rhesus thành 1 chuỗi (bạn có thể điều chỉnh định dạng)
# def join_blood(row):
#     blood = str(row.get('nhóm máu', '')).replace('"', '').replace(' ', '')
#     rh = str(row.get('rhesus', '')).replace('"', '').replace(' ', '')
#     return blood + rh

# pivoted['Nhóm máu ghi'] = pivoted.apply(join_blood, axis=1)

# # 3. Đọc file sum_report.xlsx (bảng đoàn)
# df_sum = pd.read_excel(sum_final, header=1)  
# print(df_sum.columns.tolist())
# # Đảm bảo tên cột ghép đúng
# df_sum.columns = [col.strip() for col in df_sum.columns]
# # Nếu cần đổi tên cho trùng khóa
# if 'Họ tên' not in df_sum.columns:
#     df_sum = df_sum.rename(columns={'Họ tên người bệnh': 'Họ tên'})
# if 'Giới tính' not in df_sum.columns:
#     df_sum = df_sum.rename(columns={'Giới tính': 'Giới tính'})
# if 'Năm sinh' not in df_sum.columns:
#     df_sum = df_sum.rename(columns={'Năm sinh': 'Năm sinh'})

# # 4. Merge lấy nhóm máu
# df_result = df_sum.merge(
#     pivoted[['Họ tên', 'Giới tính', 'Năm sinh', 'Nhóm máu ghi']],
#     on=['Họ tên', 'Giới tính', 'Năm sinh'],
#     how='left'
# )

# # 5. Ghi đè vào cột 'Nhóm máu' hoặc thêm mới nếu chưa có (cột S là vị trí 18, index 17)
# if 'Nhóm máu' in df_result.columns:
#     df_result['Nhóm máu'] = df_result['Nhóm máu ghi']
# else:
#     df_result.insert(17, 'Nhóm máu', df_result['Nhóm máu ghi'])

# df_result = df_result.drop(columns=['Nhóm máu ghi'])

# # 6. Xuất lại file Excel kết quả
# df_result.to_excel('sum_report_co_nhom_mau.xlsx', index=False)
# print("Đã xuất file sum_report_co_nhom_mau.xlsx!")