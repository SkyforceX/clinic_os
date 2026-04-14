import os
from pathlib import Path
from django.conf import settings
import pandas as pd
import openpyxl
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment, PatternFill, Border, Side
from datetime import datetime
import re
import pickle


def save_df(df, filename):
    temp_dir = Path(settings.MEDIA_ROOT) / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)  # Tạo thư mục nếu chưa có

    output_path = temp_dir / filename  # Ghép đường dẫn tới file trong thư mục temp

    with open(output_path, "wb") as f:
        pickle.dump(df, f)

    # return output_path  # Trả về đường dẫn để sử dụng tiếp nếu cần
    print("Đã lưu DataFrame vào:", output_path)

def convert_to_excel():
    # Bước 1: Mở file .pkl
    with open("D:/Code/Project/Django project/VMD/unicore/media/temp/imaging_temp.pkl", "rb") as f:
        df = pickle.load(f)

    # Bước 2: Kiểm tra và ghi ra file Excel
    if isinstance(df, pd.DataFrame):
        df.to_excel("imaging_result_pkl.xlsx", index=False)
        print("✅ Đã ghi thành công file Excel.")
    else:
        print("❌ File .pkl không chứa DataFrame.")

    df.to_excel("imaging_pkl.xlsx", index=False)
convert_to_excel()

def clinical_test_to_excel():
    clinical_temp_path = "D:/Code/Project/Django project/VMD/unicore/media/temp/clinical_temp.pkl"
    test_temp_path = "D:/Code/Project/Django project/VMD/unicore/media/temp/test_temp.pkl"
     # Load từ pickle
    with open(clinical_temp_path, "rb") as f:
        df1 = pickle.load(f)
    with open(test_temp_path, "rb") as g:
        df2 = pickle.load(g)

    def normalize_string(s):
        return str(s).strip().upper()

    df1['Họ tên chuẩn hóa'] = df1['Họ tên'].apply(normalize_string)
    df1['Giới tính chuẩn hóa'] = df1['Giới tính'].apply(normalize_string)
    df1['Năm sinh'] = df1['Năm sinh'].apply(lambda x: str(int(float(x))) if pd.notna(x) else "")

    df2['Họ tên chuẩn hóa'] = df2['Họ tên người bệnh'].apply(normalize_string)
    df2['Giới tính chuẩn hóa'] = df2['Giới tính'].apply(normalize_string)
    df2['Năm sinh'] = df2['Năm sinh'].apply(lambda x: str(int(float(x))) if pd.notna(x) else "")

    ds_yeu_cau = [
        'WBC', 'NEU %', 'RBC', 'HGB', 'MCV', 'MCH', 'PLT',
        'Định lượng Ure', 'Định lượng Creatinin', 'eGFR (CKD-EPI)',
        'Protein', 'Leukocytes', 'Nitrites', 'Blood',
        'Định lượng Glucose',
        'Đo hoạt độ AST (GOT)', 'Đo hoạt độ ALT (GPT)', 'Đo hoạt độ GGT',
        'Định lượng Triglycerid', 'Định lượng HDL-C', 'Định lượng LDL-C',
        'Định lượng Acid Uric', 'Bạch cầu', 'Nấm', 'Trichomonas Vaginalis'
    ]

    # df2_filtered = df2[df2['Yêu cầu'].isin(ds_yeu_cau)]

    def safe_value(x):
        allowed_strings = {'Negative', 'Positive', '1+', '2+', '3+', '4+', '+', '++', '+++', '++++'}
        if pd.isna(x):
            return ""

        # Nếu là chuỗi dạng số có dấu nháy (ví dụ: "'123.4")
        if isinstance(x, str):
            x = x.strip().lstrip("'")  # bỏ leading space và dấu nháy '
            
            # Nếu sau xử lý mà chuỗi là số thì convert
            if re.fullmatch(r'^-?\d+(\.\d+)?$', x):
                return float(x)

            # Nếu thuộc allowed_strings
            if x.upper() in allowed_strings:
                return x.upper()

            return ''

        # Nếu là số thực sự
        try:
            float(x)
            return x
        except:
            return ''
    df2_filtered = df2[df2['Yêu cầu'].isin(ds_yeu_cau)].copy()
    # df2_filtered['Kết quả'] = df2_filtered['Kết quả'].apply(safe_value)

    # before_count = df2_filtered.shape[0]
    # after_count = df2_filtered[df2_filtered['Kết quả'] != ""].shape[0]
    # print(f"Số lượng dòng hợp lệ sau xử lý: {after_count}/{before_count}")

    pivot_df = df2_filtered.pivot_table(
        index=['Họ tên chuẩn hóa', 'Giới tính chuẩn hóa', 'Năm sinh'],
        columns='Yêu cầu',
        values='Kết quả',
        aggfunc='first'
    ).reset_index()

    merged_df = pd.merge(
        df1,
        pivot_df,
        how='left',
        on=['Họ tên chuẩn hóa', 'Giới tính chuẩn hóa', 'Năm sinh']
    )
    merged_df.to_excel("merged.xlsx", index=False)

clinical_test_to_excel()
# def clinical_test_to_excel(df, output_path):
#     clinical_temp_path = "D:/Code/Project/Django project/VMD/unicore/media/temp/clinical_temp.pkl"
#     test_temp_path = "D:/Code/Project/Django project/VMD/unicore/media/temp/test_temp.pkl"
#     with open(clinical_temp_path, "rb") as f:
#         df1 = pickle.load(f)
#     with open(test_temp_path, "rb") as g:
#         df2 = pickle.load(g)

#     def normalize_string(s):
#         return str(s).strip().upper()

#     df1['Họ tên chuẩn hóa'] = df1['Họ tên'].apply(normalize_string)
#     df1['Giới tính chuẩn hóa'] = df1['Giới tính'].apply(normalize_string)
#     df1['Năm sinh'] = df1['Năm sinh'].apply(lambda x: str(int(float(x))) if pd.notna(x) else "")

#     df2['Họ tên chuẩn hóa'] = df2['Họ tên người bệnh'].apply(normalize_string)
#     df2['Giới tính chuẩn hóa'] = df2['Giới tính'].apply(normalize_string)
#     df2['Năm sinh'] = df2['Năm sinh'].apply(lambda x: str(int(float(x))) if pd.notna(x) else "")

#     ds_yeu_cau = [
#         'WBC', 'NEU %', 'RBC', 'HGB', 'MCV', 'MCH', 'PLT',
#         'Định lượng Ure', 'Định lượng Creatinin', 'eGFR (CKD-EPI)',
#         'Protein', 'Leukocytes', 'Nitrites', 'Blood',
#         'Định lượng Glucose',
#         'Đo hoạt độ AST (GOT)', 'Đo hoạt độ ALT (GPT)', 'Đo hoạt độ GGT',
#         'Định lượng Triglycerid', 'Định lượng HDL-C', 'Định lượng LDL-C',
#         'Định lượng Acid Uric', 'Bạch cầu', 'Nấm', 'Trichomonas Vaginalis'
#     ]

#     df2_filtered = df2[df2['Yêu cầu'].isin(ds_yeu_cau)]



#     pivot_df = df2_filtered.pivot_table(
#         index=['Họ tên chuẩn hóa', 'Giới tính chuẩn hóa', 'Năm sinh'],
#         columns='Yêu cầu',
#         values='Kết quả',
#         aggfunc='first'
#     ).reset_index()

#     merged_df = pd.merge(
#         df1,
#         pivot_df,
#         how='left',
#         on=['Họ tên chuẩn hóa', 'Giới tính chuẩn hóa', 'Năm sinh']
#     )

#     merged_df.to_excel("test_data3.xlsx", index=False)



def run_py4(clinical_temp_path: Path, test_temp_path: Path):
     # Load từ pickle
    with open(clinical_temp_path, "rb") as f:
        df1 = pickle.load(f)
    with open(test_temp_path, "rb") as g:
        df2 = pickle.load(g)

    def normalize_string(s):
        return str(s).strip().upper()

    df1['Họ tên chuẩn hóa'] = df1['Họ tên'].apply(normalize_string)
    df1['Giới tính chuẩn hóa'] = df1['Giới tính'].apply(normalize_string)
    df1['Năm sinh'] = df1['Năm sinh'].apply(lambda x: str(int(float(x))) if pd.notna(x) else "")

    df2['Họ tên chuẩn hóa'] = df2['Họ tên người bệnh'].apply(normalize_string)
    df2['Giới tính chuẩn hóa'] = df2['Giới tính'].apply(normalize_string)
    df2['Năm sinh'] = df2['Năm sinh'].apply(lambda x: str(int(float(x))) if pd.notna(x) else "")

    ds_yeu_cau = [
        'WBC', 'NEU %', 'RBC', 'HGB', 'MCV', 'MCH', 'PLT',
        'Định lượng Ure', 'Định lượng Creatinin', 'eGFR (CKD-EPI)',
        'Protein', 'Leukocytes', 'Nitrites', 'Blood',
        'Định lượng Glucose',
        'Đo hoạt độ AST (GOT)', 'Đo hoạt độ ALT (GPT)', 'Đo hoạt độ GGT',
        'Định lượng Triglycerid', 'Định lượng HDL-C', 'Định lượng LDL-C',
        'Định lượng Acid Uric', 'Bạch cầu', 'Nấm', 'Trichomonas Vaginalis'
    ]

    # df2_filtered = df2[df2['Yêu cầu'].isin(ds_yeu_cau)]

    def safe_value(x):
        allowed_strings = {'Negative', 'Positive', '1+', '2+', '3+', '4+', '+', '++', '+++', '++++'}
        if pd.isna(x):
            return ""

        # Nếu là chuỗi dạng số có dấu nháy (ví dụ: "'123.4")
        if isinstance(x, str):
            x = x.strip().lstrip("'")  # bỏ leading space và dấu nháy '
            
            # Nếu sau xử lý mà chuỗi là số thì convert
            if re.fullmatch(r'^-?/d+(/./d+)?$', x):
                return float(x)

            # Nếu thuộc allowed_strings
            if x.upper() in allowed_strings:
                return x.upper()

            return ''

        # Nếu là số thực sự
        try:
            float(x)
            return x
        except:
            return ''
    df2_filtered = df2[df2['Yêu cầu'].isin(ds_yeu_cau)]
    # df2_filtered['Kết quả'] = df2_filtered['Kết quả'].apply(safe_value)

    print(df2['Kết quả'])
    return ''

    # before_count = df2_filtered.shape[0]
    # after_count = df2_filtered[df2_filtered['Kết quả'] != ""].shape[0]
    # print(f"Số lượng dòng hợp lệ sau xử lý: {after_count}/{before_count}")

    pivot_df = df2_filtered.pivot_table(
        index=['Họ tên chuẩn hóa', 'Giới tính chuẩn hóa', 'Năm sinh'],
        columns='Yêu cầu',
        values='Kết quả',
        aggfunc='first'
    ).reset_index()

    merged_df = pd.merge(
        df1,
        pivot_df,
        how='left',
        on=['Họ tên chuẩn hóa', 'Giới tính chuẩn hóa', 'Năm sinh']
    )

    print(merged_df.columns)
    return ''

    def safe_float(x):
        try:
            if pd.isna(x):
                return None
            if isinstance(x, str):
                x = x.strip().lstrip("'")  # bỏ dấu nháy và khoảng trắng
                if x.upper() in ['Negative', 'Positive', '1+', '2+', '3+', '4+', '+', '++', '+++', '++++', '+-']:
                    return None
            return float(x)
        except:
            return None


    def soi_tuoi_huyet_trang(row):
        gender = str(row.get('Giới tính', '')).strip().upper()
        pk = str(row.get('Sản phụ khoa', '')).strip().upper()

        # Nếu Sản phụ khoa là TD thì luôn trả TD
        if pk == "TD":
            return "TD"

        # Lấy các giá trị xét nghiệm
        bc_raw = row.get('Bạch cầu', None)
        nam_raw = row.get('Nấm', None)
        tv_raw = row.get('Trichomonas Vaginalis', None)

        # Nếu tất cả các chỉ số đều trống và là nam → để trống
        if all(pd.isna(v) or str(v).strip() == '' for v in [bc_raw, nam_raw, tv_raw]) and 'NAM' in gender:
            return ""

        try:
            # Xử lý các chỉ số soi tươi
            bc_abnormal = False
            if bc_raw:
                try:
                    if '-' in bc_raw:
                        parts = bc_raw.split('-')
                        bc_val = safe_float(parts[-1])  # lấy giá trị cao nhất trong khoảng
                    else:
                        bc_val = safe_float(bc_raw)
                    bc_abnormal = bc_val > 20
                except:
                    bc_abnormal = False # xem như là BT nếu có lỗi

            nam_abnormal = str(nam_raw).strip().upper() in ['1+', '2+', '3+', '4+', '+', '++', '+++', '++++']
            tv_abnormal = str(tv_raw).strip().upper() == 'POSITIVE'

            # Nếu bất kỳ chỉ số nào bất thường
            if bc_abnormal or nam_abnormal or tv_abnormal:
                return "TD"
            elif bc_abnormal and pk == "BT":    
                return "BT"
            else:
                return "BT"
        except Exception as e:
            return e

    def tong_phan_tich(row):
        keys = ['WBC', 'NEU %', 'RBC', 'MCV', 'PLT']
        # if any(pd.isna(row.get(k)) for k in keys):
        #     return ""
        try:
            wbc = safe_float(row['WBC'])
            neu = safe_float(row['NEU %'])
            rbc = safe_float(row['RBC'])
            mcv = safe_float(row['MCV'])
            plt = safe_float(row['PLT'])

            if not (2 < wbc < 14): return "TD"
            if neu >= 90: return "TD"
            if not (3.5 < rbc < 6): return "TD"
            if mcv <= 80: return "TD"
            if not (100 < plt < 450): return "TD"

            return "BT"
        except Exception as e:
            return e

    def men_gan(row):
        keys = ['Đo hoạt độ AST (GOT)', 'Đo hoạt độ ALT (GPT)']
        # if any(pd.isna(row.get(k)) for k in keys):
        #     return ""
        try:
            ast = safe_float(row[keys[0]])
            alt = safe_float(row[keys[1]])
            if ast >= 90 or alt >= 90:
                return "TD"
            return "BT"
        except Exception as e:
            return e

    def chuc_nang_than(row):
        key = 'eGFR (CKD-EPI)'
        # if pd.isna(row.get(key)):
        #     return ""
        try:
            val = safe_float(row[key])
            return "BT" if val > 80 else "TD"
        except Exception as e:
            return e

    def duong_huyet(row):
        key = 'Định lượng Glucose'
        val = row.get(key)
        # if pd.isna(val):
        #     return ""
        try:
            val = safe_float(val)
            return "BT" if 60 <= val <= 129 else "TD"
        except Exception as e:
            return e

    def lipid(row):
        keys = ['Định lượng Triglycerid', 'Định lượng LDL-C', 'Định lượng HDL-C']
        # if any(pd.isna(row.get(k)) for k in keys):
        #     return ""
        try:
            tg = safe_float(row[keys[0]])
            ldl = safe_float(row[keys[1]])
            hdl = safe_float(row[keys[2]])
            if tg >= 150 or ldl >= 129 or hdl <= 40:
                return "TD"
            return "BT"
        except Exception as e:
            return e

    def sinh_hoa_khac(row):
        key = 'Định lượng Acid Uric'
        # if pd.isna(row.get(key)):
        #     return ""
        try:
            val = safe_float(row[key])
            gender = str(row['Giới tính']).strip().upper()
            if ('NAM' in gender and val >= 420) or ('NỮ' in gender and val >= 360):
                return "TD"
            return "BT"
        except Exception as e:
            return e

    def nuoc_tieu(row):
        keys = ['Protein', 'Leukocytes', 'Nitrites', 'Blood']
        # if all(pd.isna(row.get(k)) for k in keys):
        #     return ""
        abnormal_values = ['POSITIVE', '2+', '3+', '4+', '++', '+++', '++++']
        try:
            values = []
            for k in keys:
                val = row.get(k, None)
                if pd.isna(val) or str(val).strip() == "":
                    values.append(None)
                    continue

                val_str = str(val).strip().upper()

                # Nếu là số và là Leukocytes hoặc Blood → kiểm tra > 100
                if k in ['Leukocytes', 'Blood']:
                    try:
                        num_val = safe_float(val_str)
                        if num_val > 100:
                            return "TD"
                    except ValueError:
                        pass  # Nếu không phải số, tiếp tục kiểm tra dạng chuỗi

                # Nếu thuộc nhóm bất thường
                if val_str in abnormal_values:
                    return "TD"

                values.append(val_str)

            # Nếu tất cả đều NEGATIVE hoặc None → BT
            if all(v is None or v == 'NEGATIVE' for v in values):
                return "BT"

            # Nếu còn giá trị thiếu → không kết luận
            if any(v is None for v in values):
                return ""

            return "TD"
        except Exception as e:
            return e

    merged_df['Soi tươi huyết trắng'] = merged_df.apply(soi_tuoi_huyet_trang, axis=1)
    merged_df['Tổng phân tích tế bào máu ngoại vi'] = merged_df.apply(tong_phan_tich, axis=1)
    merged_df['Men gan'] = merged_df.apply(men_gan, axis=1)
    merged_df['Chức năng thận'] = merged_df.apply(chuc_nang_than, axis=1)
    merged_df['Đường huyết lúc đói'] = merged_df.apply(duong_huyet, axis=1)
    merged_df['Xét nghiệm lipid máu'] = merged_df.apply(lipid, axis=1)
    merged_df['Sinh hóa khác'] = merged_df.apply(sinh_hoa_khac, axis=1)
    merged_df['Tổng phân tích nước tiểu'] = merged_df.apply(nuoc_tieu, axis=1)

    merged_df.drop(columns=[col for col in ds_yeu_cau if col in merged_df.columns], inplace=True)
    merged_df.drop(columns=['Họ tên chuẩn hóa', 'Giới tính chuẩn hóa'], inplace=True)

    ## Đảm bảo 'Các vấn đề cần lưu ý' và 'Phân loại sức khỏe' nằm cuối cùng
    cols = [col for col in merged_df.columns if col not in ['Các vấn đề cần lưu ý', 'Phân loại sức khỏe']]
    if 'Các vấn đề cần lưu ý' in merged_df.columns:
        cols.append('Các vấn đề cần lưu ý')
    if 'Phân loại sức khỏe' in merged_df.columns:
        cols.append('Phân loại sức khỏe')
    merged_df = merged_df[cols]

    # Lưu lại vào pickle
    # save_df(merged_df, "merge_clinical_test_temp2.pkl")
    with open("D:/Code/Project/Django project/VMD/unicore/media/temp/merge_clinical_test_temp2.pkl", "wb") as f:
        pickle.dump(merged_df, f)

    # Bước 1: Mở file .pkl
    with open("D:/Code/Project/Django project/VMD/unicore/media/temp/merge_clinical_test_temp2.pkl", "rb") as fg:
        df_x = pickle.load(fg)

    # Bước 2: Kiểm tra và ghi ra file Excel
    if isinstance(df_x, pd.DataFrame):
        df_x.to_excel("merge_clinical_test_temp4.xlsx", index=False)
        print("✅ Đã ghi thành công file Excel.")
    else:
        print("❌ File .pkl không chứa DataFrame.")


clinical_temp_path = "D:/Code/Project/Django project/VMD/unicore/media/temp/clinical_temp.pkl"
test_temp_path = "D:/Code/Project/Django project/VMD/unicore/media/temp/test_temp.pkl"
# run_py4(clinical_temp_path, test_temp_path)