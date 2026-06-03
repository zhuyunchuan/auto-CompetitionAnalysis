import os
import sys
import json
import argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

DEFAULT_HK_CSV = os.path.join(
    PROJECT_ROOT, "results", "hikvision_specs_all_20260519_032013", "specs_wide.csv"
)
DEFAULT_DAHUA_CSV = os.path.join(
    PROJECT_ROOT, "results", "dahua_specs_all_20260519_032007", "specs_wide.csv"
)
DELIVERY_HK = os.path.join(PROJECT_ROOT, "delivery", "wide", "hikvision_specs_wide.csv")
DELIVERY_DAHUA = os.path.join(PROJECT_ROOT, "delivery", "wide", "dahua_specs_wide.csv")


def find_latest_wide_csv(brand):
    results_dir = os.path.join(PROJECT_ROOT, "results")
    if not os.path.isdir(results_dir):
        return None
    candidates = []
    for d in os.listdir(results_dir):
        if brand in d.lower() and "specs" in d.lower():
            full = os.path.join(results_dir, d, "specs_wide.csv")
            if os.path.isfile(full):
                candidates.append(full)
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0]


def resolve_csv(path, brand):
    if path and os.path.isfile(path):
        return path
    for candidate in [
        os.path.join(PROJECT_ROOT, "delivery", "wide", f"{brand}_specs_wide.csv"),
        os.path.join(PROJECT_ROOT, "delivery", "wide", f"{brand}_specs_wide.csv"),
    ]:
        if os.path.isfile(candidate):
            return candidate
    found = find_latest_wide_csv(brand)
    if found:
        return found
    print(f"[ERROR] Cannot find {brand} wide CSV, please specify --{brand}-csv")
    sys.exit(1)


def run_match_step(hk_csv, dahua_csv, output_dir, threshold, top_k):
    from model_matcher import run_match
    return run_match(hk_csv, dahua_csv, output_dir, threshold, top_k)


def run_compare_step(hk_csv, dahua_csv, mapping_csv, output_dir):
    from param_comparator import run_compare
    return run_compare(hk_csv, dahua_csv, mapping_csv, output_dir)


def run_report_step(hk_csv, dahua_csv, mapping_csv, diff_csv, output_path):
    import pandas as pd
    from analysis_report import generate_report
    mapping_df = pd.read_csv(mapping_csv, encoding="utf-8-sig")
    diff_df = pd.read_csv(diff_csv, encoding="utf-8-sig")
    hk_df = pd.read_csv(hk_csv, low_memory=False)
    dahua_df = pd.read_csv(dahua_csv, low_memory=False)
    generate_report(mapping_df, diff_df, hk_df, dahua_df, output_path)


def run_all(args):
    hk_csv = resolve_csv(args.hk_csv, "hikvision")
    dahua_csv = resolve_csv(args.dahua_csv, "dahua")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or os.path.join(PROJECT_ROOT, "results", f"analysis_{run_id}")
    os.makedirs(output_dir, exist_ok=True)

    print(f"=" * 60)
    print(f"  Competitor Analysis Pipeline")
    print(f"  Run ID: {run_id}")
    print(f"  Output: {output_dir}")
    print(f"=" * 60)

    print(f"\n[Step 1/3] Model Matching...")
    mapping_csv = os.path.join(output_dir, "model_mapping.csv")
    if os.path.isfile(mapping_csv) and not args.force:
        print(f"  [SKIP] Mapping file exists: {mapping_csv}")
        import pandas as pd
        mapping_df = pd.read_csv(mapping_csv, encoding="utf-8-sig")
    else:
        mapping_df = run_match_step(hk_csv, dahua_csv, output_dir, args.threshold, args.top_k)

    if mapping_df.empty:
        print("[WARN] No mappings found, skipping remaining steps")
        return

    print(f"\n[Step 2/3] Parameter Comparison...")
    diff_csv = os.path.join(output_dir, "param_diff.csv")
    if os.path.isfile(diff_csv) and not args.force:
        print(f"  [SKIP] Diff file exists: {diff_csv}")
        import pandas as pd
        diff_df = pd.read_csv(diff_csv, encoding="utf-8-sig")
    else:
        diff_df = run_compare_step(hk_csv, dahua_csv, mapping_csv, output_dir)

    print(f"\n[Step 3/3] Report Generation...")
    report_path = os.path.join(output_dir, "competitor_analysis.xlsx")
    run_report_step(hk_csv, dahua_csv, mapping_csv, diff_csv, report_path)

    print(f"\n{'=' * 60}")
    print(f"  Analysis Complete!")
    print(f"  Mappings: {len(mapping_df)}")
    print(f"  Diff records: {len(diff_df)}")
    print(f"  Report: {report_path}")
    print(f"{'=' * 60}")


def run_match_only(args):
    hk_csv = resolve_csv(args.hk_csv, "hikvision")
    dahua_csv = resolve_csv(args.dahua_csv, "dahua")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or os.path.join(PROJECT_ROOT, "results", f"analysis_{run_id}")
    run_match_step(hk_csv, dahua_csv, output_dir, args.threshold, args.top_k)


def run_compare_only(args):
    hk_csv = resolve_csv(args.hk_csv, "hikvision")
    dahua_csv = resolve_csv(args.dahua_csv, "dahua")
    output_dir = os.path.dirname(args.mapping_csv)
    run_compare_step(hk_csv, dahua_csv, args.mapping_csv, output_dir)


def run_report_only(args):
    hk_csv = resolve_csv(args.hk_csv, "hikvision")
    dahua_csv = resolve_csv(args.dahua_csv, "dahua")
    run_report_step(hk_csv, dahua_csv, args.mapping_csv, args.diff_csv, args.output)


def main():
    parser = argparse.ArgumentParser(
        description="Competitor Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_analysis.py all
  python run_analysis.py all --threshold 0.6 --top-k 3
  python run_analysis.py match --hk-csv data/hk.csv --dahua-csv data/dahua.csv
  python run_analysis.py compare --mapping-csv results/analysis_xxx/model_mapping.csv
  python run_analysis.py report --mapping-csv ... --diff-csv ... --output report.xlsx
        """
    )
    sub = parser.add_subparsers(dest="command")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--hk-csv", default=None, help="Hikvision wide CSV")
    common.add_argument("--dahua-csv", default=None, help="Dahua wide CSV")
    common.add_argument("--output-dir", default=None, help="Output directory")
    common.add_argument("--threshold", type=float, default=0.5, help="Min confidence (default: 0.5)")
    common.add_argument("--top-k", type=int, default=5, help="Max matches per model (default: 5)")
    common.add_argument("--force", action="store_true", help="Force re-run even if outputs exist")

    p_all = sub.add_parser("all", parents=[common], help="Run full pipeline (match + compare + report)")
    p_match = sub.add_parser("match", parents=[common], help="Run model matching only")
    p_compare = sub.add_parser("compare", parents=[common], help="Run parameter comparison only")
    p_compare.add_argument("--mapping-csv", required=True, help="Model mapping CSV")
    p_report = sub.add_parser("report", parents=[common], help="Generate report only")
    p_report.add_argument("--mapping-csv", required=True)
    p_report.add_argument("--diff-csv", required=True)
    p_report.add_argument("--output", required=True, help="Output Excel path")

    args = parser.parse_args()
    if args.command == "all":
        run_all(args)
    elif args.command == "match":
        run_match_only(args)
    elif args.command == "compare":
        run_compare_only(args)
    elif args.command == "report":
        run_report_only(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
