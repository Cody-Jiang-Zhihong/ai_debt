# cli.py
# Author: Cody
import argparse
from pathlib import Path
from scanner import scan_repo
from visualize import export_csv, render_html


def main():
    parser = argparse.ArgumentParser(description="AI Code Hotspot & Tech Debt Scanner")
    parser.add_argument(
        "--repo",
        type=str,
        default=".",
        help="Path to git repo root",
    )
    parser.add_argument(
        "--since",
        type=str,
        default="2023-01-01",
        help="Date since to consider AI impact (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    file_metrics, bucket_metrics, pr_metrics = scan_repo(root, since=args.since)
    reports_dir = export_csv(root, file_metrics, bucket_metrics, pr_metrics)
    html_path = render_html(root, reports_dir, file_metrics, bucket_metrics, pr_metrics)

    print(f"[+] Files analyzed: {len(file_metrics)}")
    print(f"[+] Reports written to: {reports_dir}")
    print(f"[+] Open {html_path} in your browser to see heatmap & charts")


if __name__ == "__main__":
    main()
