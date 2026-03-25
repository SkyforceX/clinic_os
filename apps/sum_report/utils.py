# utils.py
import os
import pickle
from pathlib import Path
from django.conf import settings


def save_df(df, filename):
    temp_dir = Path(settings.MEDIA_ROOT) / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)  # Tạo thư mục nếu chưa có

    output_path = temp_dir / filename  # Ghép đường dẫn tới file trong thư mục temp

    with open(output_path, "wb") as f:
        pickle.dump(df, f)

    return output_path  # Trả về đường dẫn để sử dụng tiếp nếu cần


def load_df(filename):
    with open(filename, "rb") as f:
        return pickle.load(f)

