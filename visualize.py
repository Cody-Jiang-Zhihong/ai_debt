# visualize.py
# Author: Cody
from pathlib import Path
import json
from typing import List
from models import FileMetrics, TimeBucketMetrics, PRMetrics


def export_csv(root: Path, files: List[FileMetrics], buckets: List[TimeBucketMetrics], prs: List[PRMetrics]):
    reports_dir = root / "ai_debt_reports"
    reports_dir.mkdir(exist_ok=True)

    # files.csv
    with (reports_dir / "files.csv").open("w", encoding="utf-8") as f:
        f.write("path,loc,ai_influence,ai_debt,dup,api,over_eng,unnecessary_abs,silent,recent_added\n")
        for fm in files:
            s = fm.smells
            f.write(
                f"{fm.path},{fm.loc},{fm.ai_influence_score:.3f},{fm.ai_debt_score:.3f},"
                f"{s.duplicate_blocks},{s.api_hallucinations},{s.over_engineering},"
                f"{s.unnecessary_abstractions},{s.silent_failures},{fm.recent_loc_added}\n"
            )

    # timeline.csv
    with (reports_dir / "timeline.csv").open("w", encoding="utf-8") as f:
        f.write("bucket,ai_debt_sum,ai_debt_avg,commits\n")
        for b in buckets:
            f.write(f"{b.bucket},{b.ai_debt_sum:.3f},{b.ai_debt_avg:.3f},{b.commits}\n")

    # pr.csv
    with (reports_dir / "prs.csv").open("w", encoding="utf-8") as f:
        f.write("id,files_touched,loc_added,ai_debt_delta,ai_risk_index,top_files\n")
        for p in prs:
            top = ";".join(p.top_files)
            f.write(
                f"{p.identifier},{p.files_touched},{p.loc_added},{p.ai_debt_delta:.3f},{p.ai_risk_index:.3f},{top}\n"
            )

    return reports_dir


def render_html(root: Path, reports_dir: Path, files: List[FileMetrics], buckets: List[TimeBucketMetrics], prs: List[PRMetrics]):
    html_path = reports_dir / "report.html"

    # ---------------------------------------------------------------------------
    # 修复后的模块热力图：Windows 路径、前两级模块聚合
    # ---------------------------------------------------------------------------
    module_scores = {}

    for fm in files:
        norm_path = fm.path.replace("\\", "/")
        parts = norm_path.split("/")

        # 至少取前两级目录，例如 dask/array
        if len(parts) >= 2:
            module = "/".join(parts[:2])
        elif len(parts) == 1:
            module = parts[0] or "(root)"
        else:
            module = "(root)"

        info = module_scores.setdefault(module, {"sum": 0.0, "count": 0})
        info["sum"] += fm.ai_debt_score
        info["count"] += 1

    modules = list(module_scores.keys())
    module_values = [module_scores[m]["sum"] / module_scores[m]["count"] for m in modules]

    # ---------------------------------------------------------------------------
    # 时间趋势
    # ---------------------------------------------------------------------------
    buckets_sorted = sorted(buckets, key=lambda b: b.bucket)
    bucket_labels = [b.bucket for b in buckets_sorted]
    bucket_debt = [b.ai_debt_avg for b in buckets_sorted]

    # ---------------------------------------------------------------------------
    # PR 风险
    # ---------------------------------------------------------------------------
    prs_sorted = sorted(prs, key=lambda p: p.ai_risk_index, reverse=True)
    pr_ids = [p.identifier for p in prs_sorted]
    pr_risks = [p.ai_risk_index for p in prs_sorted]

    # ---------------------------------------------------------------------------
    # HTML 输出
    # ---------------------------------------------------------------------------
    with html_path.open("w", encoding="utf-8") as f:
        f.write(
            f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>AI Tech Debt Report</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body {{ font-family: sans-serif; margin: 20px; }}
    .chart {{ width: 100%; max-width: 1000px; height: 400px; margin-bottom: 40px; }}
  </style>
</head>
<body>
  <h1>AI 技术债热力图 & 趋势</h1>

  <h2>模块 AI 技术债分布（热力图）</h2>
  <div id="heatmap" class="chart"></div>

  <h2>AI 债务趋势（按时间）</h2>
  <div id="timeline" class="chart"></div>

  <h2>PR 风险指数 Top</h2>
  <div id="prrisk" class="chart"></div>

  <script>
    // -------------------------------
    // Heatmap 数据
    // -------------------------------
    var modules = {json.dumps(modules)};
    var moduleValues = {json.dumps(module_values)};

    var heatData = [{{
      x: modules,
      y: ["AI Debt"],
      z: [moduleValues],
      type: 'heatmap',
      colorscale: 'Reds'
    }}];

    Plotly.newPlot('heatmap', heatData, {{title: 'Module AI Tech Debt Heatmap'}});

    // -------------------------------
    // 时间趋势
    // -------------------------------
    var tlData = [{{
      x: {json.dumps(bucket_labels)},
      y: {json.dumps(bucket_debt)},
      type: 'scatter',
      mode: 'lines+markers'
    }}];

    Plotly.newPlot('timeline', tlData, {{title: 'AI Debt Trend Over Time'}});

    // -------------------------------
    // PR 风险指数
    // -------------------------------
    var prData = [{{
      x: {json.dumps(pr_ids)},
      y: {json.dumps(pr_risks)},
      type: 'bar'
    }}];

    Plotly.newPlot('prrisk', prData, {{title: 'PR Risk Index'}});

  </script>
</body>
</html>
"""
        )

    return html_path
