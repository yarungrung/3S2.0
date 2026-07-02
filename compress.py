import gzip
import shutil
from pathlib import Path

data_dir = Path("backend/data/graphs")
for name in ("walk", "drive", "rail"):
    raw_file = data_dir / f"{name}.graphml"
    gz_file = data_dir / f"{name}.graphml.gz"
    if raw_file.exists():
        print(f"正在壓縮 {raw_file.name} ...")
        with open(raw_file, "rb") as f_in:
            with gzip.open(gz_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"成功生成: {gz_file.name} (大小已減少約 85%)")
    else:
        print(f"找不到檔案: {raw_file.name}，跳過。")
