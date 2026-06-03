import pandas as pd
import numpy as np
import re
import json
import os
from datetime import datetime
from collections import defaultdict


FIELD_WEIGHTS = {
    "resolution": 0.25,
    "lens_type": 0.15,
    "focal_length": 0.10,
    "supplement_light": 0.12,
    "light_range": 0.08,
    "protection": 0.08,
    "aperture": 0.07,
    "ai_function": 0.10,
    "compression": 0.05,
}

RESOLUTION_MAP = {
    "1.0 mp": 1, "1mp": 1, "1.3 mp": 1.3, "1.3mp": 1.3,
    "2 mp": 2, "2mp": 2, "2.0 mp": 2, "1080p": 2, "full hd": 2,
    "3 mp": 3, "3mp": 3, "3.0 mp": 3,
    "4 mp": 4, "4mp": 4, "4.0 mp": 4, "2k": 4,
    "5 mp": 5, "5mp": 5, "5.0 mp": 5,
    "6 mp": 6, "6mp": 6,
    "8 mp": 8, "8mp": 8, "4k": 8, "4k ultra hd": 8, "uhd": 8,
    "12 mp": 12, "12mp": 12,
    "16 mp": 16, "16mp": 16,
    "24 mp": 24, "24mp": 24,
    "32 mp": 32, "32mp": 32,
}

LENS_CATEGORIES = {
    "fixed": ["fixed", "prime", "fixed focal", "fixed-focal"],
    "varifocal": ["varifocal", "motorized", "zoom", "auto-focus"],
    "fisheye": ["fisheye", "panoramic", "360", "180"],
}

LIGHT_CATEGORIES = {
    "colorvu": ["colorvu", "full-color", "full color", "color night vision"],
    "ir": ["ir", "infrared", "ir led"],
    "dual_light": ["dual light", "smart dual light", "activelight", "smart light"],
    "laser": ["laser"],
    "none": [],
}


def parse_resolution(val):
    if pd.isna(val) or not val:
        return None
    s = str(val).strip().lower()
    for pattern, mp in sorted(RESOLUTION_MAP.items(), key=lambda x: -len(x[0])):
        if pattern in s:
            return mp
    m = re.search(r"(\d+)\s*x\s*(\d+)", s)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        return round(w * h / 1_000_000, 1)
    m = re.search(r"(\d+(?:\.\d+)?)\s*mp", s)
    if m:
        return float(m.group(1))
    return None


def parse_focal_length(val):
    if pd.isna(val) or not val:
        return None
    s = str(val).strip().lower()
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*mm", s)
    if len(nums) == 1:
        return ("fixed", float(nums[0]))
    if len(nums) >= 2:
        return ("varifocal", float(nums[0]), float(nums[-1]))
    return None


def parse_protection(val):
    if pd.isna(val) or not val:
        return set()
    s = str(val).strip()
    result = set()
    for m in re.finditer(r"IP\s*(\d{2})", s, re.IGNORECASE):
        result.add(f"IP{m.group(1)}")
    for m in re.finditer(r"IK\s*(\d{2})", s, re.IGNORECASE):
        result.add(f"IK{m.group(1)}")
    if "vandal" in s.lower():
        result.add("vandal-proof")
    if "anti-corrosion" in s.lower() or "anticorrosion" in s.lower():
        result.add("anti-corrosion")
    return result


def classify_lens(val):
    if pd.isna(val) or not val:
        return None
    s = str(val).strip().lower()
    for cat, keywords in LENS_CATEGORIES.items():
        for kw in keywords:
            if kw in s:
                return cat
    return None


def classify_light(val):
    if pd.isna(val) or not val:
        return "none"
    s = str(val).strip().lower()
    for cat, keywords in LIGHT_CATEGORIES.items():
        if cat == "none":
            continue
        for kw in keywords:
            if kw in s:
                return cat
    return "none"


def parse_light_range(val):
    if pd.isna(val) or not val:
        return None
    s = str(val).strip().lower()
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)", s)
    if nums:
        return float(max(nums, key=float))
    nums = re.findall(r"(\d+(?:\.\d+)?)", s)
    if nums:
        return float(max(nums, key=float))
    return None


def parse_aperture(val):
    if pd.isna(val) or not val:
        return None
    s = str(val).strip()
    m = re.search(r"[fF]/\s*(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1))
    m = re.search(r"[fF]\s*(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1))
    return None


def extract_features(row, field_map):
    features = {}

    res_val = row.get(field_map.get("resolution"))
    features["resolution"] = parse_resolution(res_val)

    lens_val = row.get(field_map.get("lens_type"))
    features["lens_type"] = classify_lens(lens_val)

    focal_val = row.get(field_map.get("focal_length"))
    features["focal_length"] = parse_focal_length(focal_val)

    light_val = row.get(field_map.get("supplement_light"))
    features["supplement_light"] = classify_light(light_val)

    range_val = row.get(field_map.get("light_range"))
    features["light_range"] = parse_light_range(range_val)

    prot_val = row.get(field_map.get("protection"))
    features["protection"] = parse_protection(prot_val)

    aper_val = row.get(field_map.get("aperture"))
    features["aperture"] = parse_aperture(aper_val)

    ai_val = row.get(field_map.get("ai_function"))
    features["ai_function"] = set() if pd.isna(ai_val) or not ai_val else set(
        re.split(r"[,;/\n]", str(ai_val))
    )

    comp_val = row.get(field_map.get("compression"))
    features["compression"] = set() if pd.isna(comp_val) or not comp_val else set(
        re.split(r"[,;/\n]", str(comp_val))
    )

    return features


def compute_similarity(feat_a, feat_b):
    scores = {}
    total_weight = 0.0
    weighted_sum = 0.0

    if feat_a["resolution"] is not None and feat_b["resolution"] is not None:
        max_res = max(feat_a["resolution"], feat_b["resolution"])
        if max_res > 0:
            scores["resolution"] = min(feat_a["resolution"], feat_b["resolution"]) / max_res
        else:
            scores["resolution"] = 1.0
        weighted_sum += FIELD_WEIGHTS["resolution"] * scores["resolution"]
        total_weight += FIELD_WEIGHTS["resolution"]

    if feat_a["lens_type"] is not None and feat_b["lens_type"] is not None:
        scores["lens_type"] = 1.0 if feat_a["lens_type"] == feat_b["lens_type"] else 0.0
        weighted_sum += FIELD_WEIGHTS["lens_type"] * scores["lens_type"]
        total_weight += FIELD_WEIGHTS["lens_type"]

    if feat_a["supplement_light"] is not None and feat_b["supplement_light"] is not None:
        if feat_a["supplement_light"] == "none" and feat_b["supplement_light"] == "none":
            scores["supplement_light"] = 1.0
        elif feat_a["supplement_light"] == feat_b["supplement_light"]:
            scores["supplement_light"] = 1.0
        else:
            scores["supplement_light"] = 0.2
        weighted_sum += FIELD_WEIGHTS["supplement_light"] * scores["supplement_light"]
        total_weight += FIELD_WEIGHTS["supplement_light"]

    if feat_a["focal_length"] is not None and feat_b["focal_length"] is not None:
        type_a = feat_a["focal_length"][0]
        type_b = feat_b["focal_length"][0]
        if type_a == type_b:
            if type_a == "fixed":
                diff = abs(feat_a["focal_length"][1] - feat_b["focal_length"][1])
                max_f = max(feat_a["focal_length"][1], feat_b["focal_length"][1])
                scores["focal_length"] = max(0, 1.0 - diff / max_f) if max_f > 0 else 1.0
            else:
                scores["focal_length"] = 0.8
        else:
            scores["focal_length"] = 0.1
        weighted_sum += FIELD_WEIGHTS["focal_length"] * scores["focal_length"]
        total_weight += FIELD_WEIGHTS["focal_length"]

    if feat_a["light_range"] is not None and feat_b["light_range"] is not None:
        max_range = max(feat_a["light_range"], feat_b["light_range"])
        if max_range > 0:
            scores["light_range"] = min(feat_a["light_range"], feat_b["light_range"]) / max_range
        else:
            scores["light_range"] = 1.0
        weighted_sum += FIELD_WEIGHTS["light_range"] * scores["light_range"]
        total_weight += FIELD_WEIGHTS["light_range"]

    if feat_a["protection"] and feat_b["protection"]:
        common = feat_a["protection"] & feat_b["protection"]
        total = feat_a["protection"] | feat_b["protection"]
        scores["protection"] = len(common) / len(total) if total else 0.0
        weighted_sum += FIELD_WEIGHTS["protection"] * scores["protection"]
        total_weight += FIELD_WEIGHTS["protection"]

    if feat_a["aperture"] is not None and feat_b["aperture"] is not None:
        max_ap = max(feat_a["aperture"], feat_b["aperture"])
        if max_ap > 0:
            scores["aperture"] = min(feat_a["aperture"], feat_b["aperture"]) / max_ap
        else:
            scores["aperture"] = 1.0
        weighted_sum += FIELD_WEIGHTS["aperture"] * scores["aperture"]
        total_weight += FIELD_WEIGHTS["aperture"]

    if feat_a["ai_function"] and feat_b["ai_function"]:
        common = feat_a["ai_function"] & feat_b["ai_function"]
        total = feat_a["ai_function"] | feat_b["ai_function"]
        scores["ai_function"] = len(common) / len(total) if total else 0.0
        weighted_sum += FIELD_WEIGHTS["ai_function"] * scores["ai_function"]
        total_weight += FIELD_WEIGHTS["ai_function"]

    overall = weighted_sum / total_weight if total_weight > 0 else 0.0
    return overall, scores


def build_feature_index(df, field_map):
    features_list = []
    for idx, row in df.iterrows():
        feat = extract_features(row, field_map)
        features_list.append(feat)
    return features_list


def find_matches(hk_df, dahua_df, hk_field_map, dahua_field_map, threshold=0.5, top_k=5):
    print(f"[matcher] Building feature index: Hikvision {len(hk_df)} models, Dahua {len(dahua_df)} models...")
    hk_features = build_feature_index(hk_df, hk_field_map)
    dahua_features = build_feature_index(dahua_df, dahua_field_map)

    matches = []
    total = len(hk_df) * len(dahua_df)
    checked = 0

    for i in range(len(hk_df)):
        hk_row = hk_df.iloc[i]
        for j in range(len(dahua_df)):
            dahua_row = dahua_df.iloc[j]
            score, dim_scores = compute_similarity(hk_features[i], dahua_features[j])
            checked += 1

            if score >= threshold:
                match_dims = [k for k, v in dim_scores.items() if v >= 0.5]
                matches.append({
                    "hikvision_model": hk_row.get("model", ""),
                    "hikvision_series_l1": hk_row.get("series_l1", ""),
                    "hikvision_subseries": hk_row.get("series_l2", hk_row.get("subseries", "")),
                    "hikvision_name": hk_row.get("name", ""),
                    "hikvision_url": hk_row.get("url", ""),
                    "dahua_model": dahua_row.get("model", ""),
                    "dahua_series_l1": dahua_row.get("series_l1", ""),
                    "dahua_subseries": dahua_row.get("series_l2", dahua_row.get("subseries", "")),
                    "dahua_name": dahua_row.get("name", ""),
                    "dahua_url": dahua_row.get("url", ""),
                    "confidence_score": round(score, 4),
                    "match_dimensions": ", ".join(sorted(match_dims)),
                    "is_manual_confirmed": False,
                })

        if (i + 1) % 50 == 0:
            print(f"  [matcher] Progress: {i+1}/{len(hk_df)} Hikvision models, {len(matches)} matches found")

    print(f"  [matcher] Total comparisons: {checked}, matches (>= {threshold}): {len(matches)}")

    matches_df = pd.DataFrame(matches)
    if len(matches_df) > 0:
        matches_df = matches_df.sort_values("confidence_score", ascending=False)
        matches_df["mapping_id"] = [f"MAP_{i+1:04d}" for i in range(len(matches_df))]

    return matches_df


def filter_top_matches(matches_df, max_per_hk=5, max_per_dahua=5):
    if matches_df.empty:
        return matches_df

    hk_count = defaultdict(int)
    dahua_count = defaultdict(int)
    keep = []

    for _, row in matches_df.iterrows():
        hk_m = row["hikvision_model"]
        dahua_m = row["dahua_model"]
        if hk_count[hk_m] < max_per_hk and dahua_count[dahua_m] < max_per_dahua:
            keep.append(row)
            hk_count[hk_m] += 1
            dahua_count[dahua_m] += 1

    return pd.DataFrame(keep).reset_index(drop=True)


def run_match(hk_csv, dahua_csv, output_dir, threshold=0.5, top_k=5):
    os.makedirs(output_dir, exist_ok=True)
    print(f"[matcher] Loading data...")
    print(f"  Hikvision: {hk_csv}")
    print(f"  Dahua: {dahua_csv}")

    hk_df = pd.read_csv(hk_csv, low_memory=False)
    dahua_df = pd.read_csv(dahua_csv, low_memory=False)

    hk_df.columns = [c.strip() for c in hk_df.columns]
    dahua_df.columns = [c.strip() for c in dahua_df.columns]

    hk_field_map = _build_hk_field_map(hk_df)
    dahua_field_map = _build_dahua_field_map(dahua_df)

    print(f"[matcher] Hikvision field mapping: {hk_field_map}")
    print(f"[matcher] Dahua field mapping: {dahua_field_map}")

    matches_df = find_matches(hk_df, dahua_df, hk_field_map, dahua_field_map, threshold, top_k)
    matches_df = filter_top_matches(matches_df, max_per_hk=top_k, max_per_dahua=top_k)

    out_csv = os.path.join(output_dir, "model_mapping.csv")
    matches_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[matcher] Saved {len(matches_df)} mappings to {out_csv}")

    meta = {
        "generated_at": datetime.now().isoformat(),
        "hikvision_source": hk_csv,
        "dahua_source": dahua_csv,
        "threshold": threshold,
        "top_k": top_k,
        "hikvision_model_count": len(hk_df),
        "dahua_model_count": len(dahua_df),
        "mapping_count": len(matches_df),
    }
    meta_path = os.path.join(output_dir, "analysis_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return matches_df


def _find_col(df, candidates):
    for c in candidates:
        for col in df.columns:
            if col.strip().lower() == c.lower():
                return col
    return None


def _build_hk_field_map(df):
    m = {}
    m["resolution"] = _find_col(df, ["Max. Resolution", "Max Resolution", "MaxResolution"])
    m["lens_type"] = _find_col(df, ["Lens", "Lens Type", "LensType"])
    m["focal_length"] = _find_col(df, ["Focal Length", "Lens Focal Length", "FocalLength"])
    m["supplement_light"] = _find_col(df, [
        "Supplement Light", "Supplement Light Type", "SupplementLight",
        "IR Light", "Supplement Light Mode",
    ])
    m["light_range"] = _find_col(df, [
        "Supplement Light Range", "IR Range", "SupplementLightRange",
        "IR Distance", "Supplement Light Distance",
    ])
    m["protection"] = _find_col(df, ["Protection", "Protection Level", "Approval/Protection"])
    m["aperture"] = _find_col(df, ["Aperture", "Max. Aperture", "Max Aperture"])
    m["ai_function"] = _find_col(df, [
        "Deep Learning Function", "Deep Learning Function Categories",
        "AI Function", "Intelligent Analytics",
    ])
    m["compression"] = _find_col(df, [
        "Video Compression", "Compression", "Compression Standard",
        "Main Stream Video Compression",
    ])
    return {k: v for k, v in m.items() if v is not None}


def _build_dahua_field_map(df):
    m = {}
    m["resolution"] = _find_col(df, ["Max. Resolution", "Max Resolution", "MaxResolution"])
    m["lens_type"] = _find_col(df, ["Lens Type", "Lens", "LensType"])
    m["focal_length"] = _find_col(df, ["Focal Length", "Lens Focal Length", "FocalLength"])
    m["supplement_light"] = _find_col(df, [
        "Supplement Light", "Supplement Light Type", "SupplementLight",
        "IR Light", "Light Type",
    ])
    m["light_range"] = _find_col(df, [
        "Illumination Distance", "Supplement Light Range", "IR Range",
        "IR Distance", "SupplementLightRange", "Supplement Light Distance",
    ])
    m["protection"] = _find_col(df, ["Protection", "Protection Level", "Approval/Protection"])
    m["aperture"] = _find_col(df, ["Max. Aperture", "Max Aperture", "Aperture"])
    m["ai_function"] = _find_col(df, [
        "Deep Learning Function", "AI Function", "Intelligent Analytics",
        "Deep Learning Function Categories",
    ])
    m["compression"] = _find_col(df, [
        "Video Compression", "Compression", "Compression Standard",
        "Main Stream Video Compression",
    ])
    return {k: v for k, v in m.items() if v is not None}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cross-brand model matching")
    parser.add_argument("--hk-csv", required=True, help="Hikvision wide CSV path")
    parser.add_argument("--dahua-csv", required=True, help="Dahua wide CSV path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--threshold", type=float, default=0.5, help="Minimum confidence threshold")
    parser.add_argument("--top-k", type=int, default=5, help="Max matches per model")
    args = parser.parse_args()
    run_match(args.hk_csv, args.dahua_csv, args.output_dir, args.threshold, args.top_k)
