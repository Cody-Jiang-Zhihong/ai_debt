# cli.py
# Author: Cody
import argparse
from pathlib import Path
from scanner import scan_repo
# from timeline import build_time_buckets
from diff_timeline import build_diff_timeline
from pr_analysis import build_pr_metrics
from visualize import export_csv, render_html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to repository root")
    parser.add_argument("--since", default="2020-01-01",
                        help="Git history since this date")
    args = parser.parse_args()

    root = Path(args.repo)

    print("📁 Scanning repository...")
    file_metrics = scan_repo(root)

    #print("📈 Building time buckets...")
    #bucket_metrics = build_time_buckets(root, file_metrics, since=args.since)
    print("📈 Building incremental diff-based timeline...")
    bucket_metrics = build_diff_timeline(root, since=args.since)


    print("🔍 Computing PR risk metrics...")
    pr_metrics = build_pr_metrics(root, file_metrics, since=args.since)

    print("📤 Exporting CSV files...")
    reports_dir = export_csv(root, file_metrics, bucket_metrics, pr_metrics)

    print("🎨 Rendering HTML dashboard...")
    html_path = render_html(root, reports_dir, file_metrics, bucket_metrics, pr_metrics)

    print("✅ Done! Report generated at:")
    print(html_path)


if __name__ == "__main__":
    main()
