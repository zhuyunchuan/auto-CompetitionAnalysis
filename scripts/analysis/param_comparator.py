import pandas as pd
import re
import os
from datetime import datetime


COMMON_FIELDS = [
    ("Max. Resolution", "Max. Resolution", "resolution"),
    ("Max Resolution", "Max Resolution", "resolution"),
    ("Lens Type", "Lens Type", "lens_type"),
    ("Lens", "Lens", "lens_type"),
    ("Focal Length", "Focal Length", "focal_length"),
    ("Aperture", "Max. Aperture", "aperture"),
    ("Max. Aperture", "Aperture", "aperture"),
    ("Supplement Light", "Supplement Light", "supplement_light"),
    ("Supplement Light Type", "Supplement Light Type", "supplement_light"),
    ("Supplement Light Range", "Illumination Distance", "light_range"),
    ("IR Range", "IR Distance", "light_range"),
    ("Protection", "Protection", "protection"),
    ("Video Compression", "Video Compression", "compression"),
    ("Main Stream", "Main Stream", "main_stream"),
    ("Min. Illumination", "Min. Illumination", "min_illumination"),
    ("Image Sensor", "Image Sensor", "sensor"),
    ("Interface", "Interface", "interface"),
    ("Deep Learning Function", "Deep Learning Function", "ai_function"),
    ("Deep Learning Function Categories", "AI Function", "ai_function"),
    ("Power Supply", "Power Supply", "power"),
    ("Power Consumption", "Power Consumption", "power_consumption"),
    ("Operating Conditions", "Operating Conditions", "operating_conditions"),
    ("Dimensions", "Dimensions", "dimensions"),
    ("Weight", "Weight", "weight"),
]


def build_field_pairs(hk_cols, dahua_cols):
    pairs = []
    for hk_name, dahua_name, code in COMMON_FIELDS:
        hk_col = _find(hk_cols, hk_name)
        dahua_col = _find(dahua_cols, dahua_name)
        if hk_col and dahua_col:
            pairs.append((hk_col, dahua_col, code))
    return pairs


def _find(cols, name):
    name_lower = name.lower().strip()
    for c in cols:
        if c.lower().strip() == name_lower:
            return c
    for c in cols:
        if name_lower in c.lower().strip():
            return c
    return None


def normalize_value(val):
    if pd.isna(val) or not val:
        return ""
    s = str(val).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u200b", "")
    return s


def compare_exact(val_a, val_b):
    a = normalize_value(val_a).lower()
    b = normalize_value(val_b).lower()
    if not a and not b:
        return "both_missing", ""
    if not a or not b:
        return "one_side_missing", f"{'Hikvision' if not a else 'Dahua'} missing"
    if a == b:
        return "match", ""
    return "value_diff", f"Hikvision: {normalize_value(val_a)} | Dahua: {normalize_value(val_b)}"


def compare_numeric(val_a, val_b):
    a_num = _extract_number(val_a)
    b_num = _extract_number(val_b)
    if a_num is None and b_num is None:
        return "both_missing", ""
    if a_num is None or b_num is None:
        return "one_side_missing", f"{'Hikvision' if a_num is None else 'Dahua'} missing"
    if abs(a_num - b_num) < 0.01:
        return "match", ""
    diff = round(a_num - b_num, 2)
    direction = "Hikvision +" if diff > 0 else "Dahua +"
    return "value_diff", f"{direction}{abs(diff)}"


def compare_set(val_a, val_b):
    a_items = _split_set(val_a)
    b_items = _split_set(val_b)
    if not a_items and not b_items:
        return "both_missing", ""
    if not a_items or not b_items:
        return "one_side_missing", f"{'Hikvision' if not a_items else 'Dahua'} missing"
    common = a_items & b_items
    if common == a_items == b_items:
        return "match", ""
    only_a = a_items - b_items
    only_b = b_items - a_items
    detail_parts = []
    if only_a:
        detail_parts.append(f"Hikvision only: {', '.join(sorted(only_a))}")
    if only_b:
        detail_parts.append(f"Dahua only: {', '.join(sorted(only_b))}")
    return "feature_diff", "; ".join(detail_parts)


COMPARISON_STRATEGY = {
    "resolution": compare_numeric,
    "focal_length": compare_exact,
    "aperture": compare_numeric,
    "supplement_light": compare_set,
    "light_range": compare_numeric,
    "protection": compare_set,
    "compression": compare_set,
    "main_stream": compare_exact,
    "min_illumination": compare_numeric,
    "sensor": compare_exact,
    "lens_type": compare_exact,
    "interface": compare_set,
    "ai_function": compare_set,
    "power": compare_exact,
    "power_consumption": compare_numeric,
    "operating_conditions": compare_exact,
    "dimensions": compare_exact,
    "weight": compare_numeric,
}

SEVERITY_RULES = {
    "resolution": "P1",
    "lens_type": "P1",
    "supplement_light": "P2",
    "light_range": "P2",
    "aperture": "P2",
    "ai_function": "P2",
    "protection": "P2",
    "compression": "P3",
    "main_stream": "P3",
    "min_illumination": "P3",
    "sensor": "P3",
    "focal_length": "P1",
    "interface": "P3",
    "power": "P3",
    "power_consumption": "P3",
    "operating_conditions": "P3",
    "dimensions": "P3",
    "weight": "P3",
}


def run_compare(hk_csv, dahua_csv, mapping_csv, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    print(f"[comparator] Loading data...")

    hk_df = pd.read_csv(hk_csv, low_memory=False)
    dahua_df = pd.read_csv(dahua_csv, low_memory=False)
    mapping_df = pd.read_csv(mapping_csv, encoding="utf-8-sig")

    hk_df.columns = [c.strip() for c in hk_df.columns]
    dahua_df.columns = [c.strip() for c in dahua_df.columns]

    hk_index = {str(row.get("model", "")).strip(): row for _, row in hk_df.iterrows()}
    dahua_index = {str(row.get("model", "")).strip(): row for _, row in dahua_df.iterrows()}

    field_pairs = build_field_pairs(hk_df.columns.tolist(), dahua_df.columns.tolist())
    print(f"[comparator] Found {len(field_pairs)} comparable field pairs")
    for hk_col, dahua_col, code in field_pairs:
        print(f"  {code}: HK[{hk_col}] <-> Dahua[{dahua_col}]")

    diffs = []
    total = len(mapping_df)

    for idx, mapping in mapping_df.iterrows():
        hk_model = str(mapping.get("hikvision_model", "")).strip()
        dahua_model = str(mapping.get("dahua_model", "")).strip()
        mapping_id = mapping.get("mapping_id", f"MAP_{idx+1:04d}")

        hk_row = hk_index.get(hk_model)
        dahua_row = dahua_index.get(dahua_model)

        if hk_row is None or dahua_row is None:
            print(f"  [WARN] Model not found: HK={hk_model} ({'OK' if hk_row is not None else 'MISSING'}), "
                  f"Dahua={dahua_model} ({'OK' if dahua_row is not None else 'MISSING'})")
            continue

        for hk_col, dahua_col, code in field_pairs:
            val_a = hk_row.get(hk_col, "")
            val_b = dahua_row.get(dahua_col, "")

            strategy = COMPARISON_STRATEGY.get(code, compare_exact)
            diff_type, diff_detail = strategy(val_a, val_b)

            severity = SEVERITY_RULES.get(code, "P3")
            if diff_type == "match" or diff_type == "both_missing":
                severity = "-"

            diffs.append({
                "mapping_id": mapping_id,
                "hikvision_model": hk_model,
                "dahua_model": dahua_model,
                "field_code": code,
                "field_name_hk": hk_col,
                "field_name_dahua": dahua_col,
                "hikvision_value": normalize_value(val_a),
                "dahua_value": normalize_value(val_b),
                "diff_type": diff_type,
                "diff_detail": diff_detail,
                "severity": severity,
            })

        if (idx + 1) % 100 == 0:
            print(f"  [comparator] Progress: {idx+1}/{total} mappings processed")

    diffs_df = pd.DataFrame(diffs)
    out_csv = os.path.join(output_dir, "param_diff.csv")
    diffs_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[comparator] Saved {len(diffs_df)} diff records to {out_csv}")

    _print_diff_summary(diffs_df)
    return diffs_df


def _extract_number(val):
    if pd.isna(val) or not val:
        return None
    s = str(val).strip().lower()
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def _split_set(val):
    if pd.isna(val) or not val:
        return set()
    s = normalize_value(val)
    items = set()
    for item in re.split(r"[,;/\n|]", s):
        item = item.strip().lower()
        if item:
            items.add(item)
    return items


def _print_diff_summary(df):
    if df.empty:
        print("[comparator] No diff records generated")
        return

    print("\n[comparator] === Diff Summary ===")
    print(f"  Total records: {len(df)}")
    print(f"  Unique mappings: {df['mapping_id'].nunique()}")

    type_counts = df["diff_type"].value_counts()
    print(f"  Diff types:")
    for t, c in type_counts.items():
        print(f"    {t}: {c} ({c/len(df)*100:.1f}%)")

    p1_diffs = df[df["severity"] == "P1"]
    if len(p1_diffs) > 0:
        print(f"  P1 (critical) differences: {len(p1_diffs)}")
        top_p1_fields = p1_diffs["field_code"].value_counts().head(5)
        for field, count in top_p1_fields.items():
            print(f"    {field}: {count}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parameter difference analysis")
    parser.add_argument("--hk-csv", required=True)
    parser.add_argument("--dahua-csv", required=True)
    parser.add_argument("--mapping-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    run_compare(args.hk_csv, args.dahua_csv, args.mapping_csv, args.output_dir)
