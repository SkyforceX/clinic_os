from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
import os
import pandas as pd
import pickle
from pathlib import Path
from django.conf import settings

# Import hàm xử lý chính
from .processing import run_full_pipeline

@login_required(login_url='authentication:staff_login')
def create_summary_report(request):
    output_file_url = None
    unexpected_data_list = None

    if request.method == 'POST':
        # Đọc trực tiếp file từ request.FILES (không lưu file upload lại)
        customer_file = request.FILES['customer_list']
        test_file = request.FILES['test_list']
        clinical_file = request.FILES['clinical_list']
        imaging_file = request.FILES['imaging_list']

        # Lấy tên công ty từ file clinical (đọc trực tiếp bằng pandas)
        df_clinical = pd.read_excel(clinical_file, header=None)
        merged_text = df_clinical.iloc[5, 2]  # Dòng 6, cột C

        if pd.notna(merged_text):
            company_name = merged_text.replace("DANH SÁCH KHÁM SỨC KHỎE ĐỊNH KỲ CBCNV ", "").strip()
        else:
            company_name = "UnknownCompany"

        safe_company_name = company_name.replace(" ", "_").replace("/", "_")
        output_filename = f"summary_report_{safe_company_name}.xlsx"
        output_path = Path(settings.MEDIA_ROOT) / output_filename

        # Reset lại stream cho file clinical vì pandas đã đọc hết file pointer
        clinical_file.seek(0)
        # Đọc lại file clinical từ đầu nếu cần đưa vào pipeline

        # Xử lý pipeline, truyền các file-like object (không phải đường dẫn!)
        unexpected_data_list = run_full_pipeline(
            customer_list=customer_file,
            test_list=test_file,
            clinical_list=clinical_file,
            imaging_list=imaging_file,
            output_path=output_path
        )

        output_file_url = settings.MEDIA_URL + output_filename

    return render(request, 'sum_report/upload.html', {
        "output_file": output_file_url,
        "unexpected_data_list": unexpected_data_list
    })

# def create_summary_report(request):
#     output_file_url = None
#     unexpected_data_list = None

#     if request.method == 'POST':
#         fs = FileSystemStorage(location=settings.MEDIA_ROOT)
#         file_customer = fs.save(request.FILES['customer_list'].name, request.FILES['customer_list'])
#         file_test = fs.save(request.FILES['test_list'].name, request.FILES['test_list'])
#         file_clinical = fs.save(request.FILES['clinical_list'].name, request.FILES['clinical_list'])
#         file_imaging = fs.save(request.FILES['imaging_list'].name, request.FILES['imaging_list'])
        
#         # ======== Lấy tên công ty từ file customer_list ========
#         clinical_list_path = Path(settings.MEDIA_ROOT) / file_clinical
#         df_clinical = pd.read_excel(clinical_list_path, header=None)

#         merged_text = df_clinical.iloc[5, 2]  # Dòng 6, cột C

#         if pd.notna(merged_text):
#             company_name = merged_text.replace("DANH SÁCH KHÁM SỨC KHỎE ĐỊNH KỲ CBCNV ", "").strip()
#         else:
#             company_name = "UnknownCompany"

#         # Đổi tên file output
#         safe_company_name = company_name.replace(" ", "_").replace("/", "_")  # tránh lỗi tên file
#         output_filename = f"summary_report_{safe_company_name}.xlsx"
#         output_path = Path(settings.MEDIA_ROOT) / output_filename

#         # Gọi xử lý chính
#         unexpected_data_list = run_full_pipeline(
#             customer_list=Path(settings.MEDIA_ROOT) / file_customer,
#             test_list=Path(settings.MEDIA_ROOT) / file_test,
#             clinical_list=Path(settings.MEDIA_ROOT) / file_clinical,
#             imaging_list=Path(settings.MEDIA_ROOT) / file_imaging,
#             output_path=output_path
#         )

#         # Trả ra URL để tải file
#         output_file_url = settings.MEDIA_URL + output_filename
        
#     return render(request, 'upload.html', {
#         "output_file": output_file_url,
#         "unexpected_data_list": unexpected_data_list
#     })
