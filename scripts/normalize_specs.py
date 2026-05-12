"""
规格数据规整脚本：将长格式 specs_long.csv/jsonl 转换为宽格式 specs_wide.csv

输入：raw crawl 输出的 specs_long.csv（或 specs_long.jsonl），每行为一个 field-value 对
输出：以型号为唯一标识的宽表 CSV，每个参数占独立列

用法：
    python scripts/normalize_specs.py <输入文件路径> [输出目录]

示例：
    python scripts/normalize_specs.py results/dahua_specs_all_20260511_134223/specs_long.csv
    python scripts/normalize_specs.py results/hikvision_specs_all_20260511_123532/specs_long.jsonl
    python scripts/normalize_specs.py specs_long.csv ./output/
"""

import csv
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path


def read_long_csv(filepath: str) -> list[dict]:
    """读取长格式 CSV，返回行列表"""
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def read_long_jsonl(filepath: str) -> list[dict]:
    """读取长格式 JSONL，返回行列表"""
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def normalize_series(series_l1: str, subseries: str) -> str:
    """
    规整系列信息：将 subseries 合并到 series_l2 字段
    输入格式中 subseries 存储的是子系列（如 IR, PTZ, Value Camera）
    """
    s1 = (series_l1 or "").strip()
    s2 = (subseries or "").strip()
    return s1, s2


def pivot_to_wide(rows: list[dict]) -> tuple[list[OrderedDict], list[str]]:
    """
    将长格式行列表转换为宽格式

    返回：(宽表行列表, 所有参数字段名列表)
    """
    # 按 model 分组，收集每个 product 的元数据和参数
    products: dict[str, dict] = {}
    all_fields: set[str] = set()

    for row in rows:
        model = (row.get("model") or "").strip()
        if not model:
            continue

        if model not in products:
            s1, s2 = normalize_series(
                row.get("series_l1", ""),
                row.get("subseries", row.get("series_l2", ""))
            )
            products[model] = {
                "brand": (row.get("brand") or "").strip(),
                "series_l1": s1,
                "series_l2": s2,
                "name": (row.get("name") or "").strip(),
                "url": (row.get("url") or "").strip(),
                "fields": {},
            }

        field_name = (row.get("field") or "").strip()
        value = (row.get("value") or "").strip()

        if field_name:
            all_fields.add(field_name)
            if field_name not in products[model]["fields"]:
                products[model]["fields"][field_name] = value
            else:
                # 同字段多条时，用换行拼接
                existing = products[model]["fields"][field_name]
                if value and value not in existing:
                    products[model]["fields"][field_name] = existing + "\n" + value

    # 构建宽表行
    sorted_fields = sorted(all_fields)
    wide_rows: list[OrderedDict] = []

    for model, prod in products.items():
        row = OrderedDict()
        row["brand"] = prod["brand"]
        row["series_l1"] = prod["series_l1"]
        row["series_l2"] = prod["series_l2"]
        row["model"] = model
        row["name"] = prod["name"]
        row["url"] = prod["url"]
        for f in sorted_fields:
            row[f] = prod["fields"].get(f, "")
        wide_rows.append(row)

    return wide_rows, sorted_fields


def write_wide_csv(
    wide_rows: list[OrderedDict],
    field_columns: list[str],
    output_path: str,
):
    """将宽表写入 CSV 文件"""
    metadata_cols = ["brand", "series_l1", "series_l2", "model", "name", "url"]
    all_columns = metadata_cols + field_columns

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        for row in wide_rows:
            writer.writerow(row)


def main():
    if len(sys.argv) < 2:
        print("用法: python normalize_specs.py <输入文件路径> [输出目录]")
        print("示例: python normalize_specs.py specs_long.csv")
        print("      python normalize_specs.py specs_long.jsonl ./output/")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else None

    if not os.path.exists(input_path):
        print(f"错误: 文件不存在 - {input_path}")
        sys.exit(1)

    ext = Path(input_path).suffix.lower()

    print(f"读取文件: {input_path}")
    if ext == ".csv":
        rows = read_long_csv(input_path)
    elif ext == ".jsonl":
        rows = read_long_jsonl(input_path)
    else:
        print(f"错误: 不支持的文件格式 '{ext}'，仅支持 .csv 和 .jsonl")
        sys.exit(1)

    print(f"  读取 {len(rows)} 条记录")

    # 转换为宽格式
    wide_rows, field_columns = pivot_to_wide(rows)
    product_count = len(wide_rows)

    print(f"  转换: {product_count} 个型号, {len(field_columns)} 个参数字段")

    # 确定输出路径
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_filename = Path(input_path).stem.replace("_long", "_wide") + ".csv"
        output_path = os.path.join(output_dir, output_filename)
    else:
        input_dir = os.path.dirname(input_path) or "."
        output_filename = Path(input_path).stem.replace("_long", "_wide") + ".csv"
        output_path = os.path.join(input_dir, output_filename)

    write_wide_csv(wide_rows, field_columns, output_path)
    print(f"输出文件: {output_path}")
    print(f"  列数: {6 + len(field_columns)} (6 元数据列 + {len(field_columns)} 参数列)")
    print(f"  行数: {product_count} (含表头)")

    # 输出简要统计
    print(f"\n字段覆盖统计 (Top 10):")
    field_counts = {}
    for f in field_columns:
        field_counts[f] = sum(1 for r in wide_rows if r.get(f, "").strip())
    for f, count in sorted(field_counts.items(), key=lambda x: -x[1])[:10]:
        pct = count / product_count * 100
        print(f"  {f}: {count}/{product_count} ({pct:.0f}%)")

    print("\n✅ 规整完成")


if __name__ == "__main__":
    main()
