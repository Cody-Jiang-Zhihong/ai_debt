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
            s = fm.smell
            f.write(
                f"{fm.path},{fm.loc},{fm.ai_influence:.3f},{fm.ai_debt_score:.3f},"
                f"{s.duplicate_blocks},{s.api_hallucinations},{s.over_engineering},"
                f"{s.unnecessary_abstractions},{s.silent_failures},{fm.recent_added}\n"
            )

    # timeline.csv
    with (reports_dir / "timeline.csv").open("w", encoding="utf-8") as f:
        f.write("bucket,ai_debt_sum,ai_debt_avg,commits\n")
        for b in buckets:
            f.write(f"{b.bucket},{b.ai_debt_sum:.3f},{b.ai_debt_avg:.3f},{b.commits}\n")

    # prs.csv
    with (reports_dir / "prs.csv").open("w", encoding="utf-8") as f:
        f.write("id,files_touched,loc_added,ai_debt_delta,ai_risk_index,top_files\n")
        for p in prs:
            top = ";".join(p.top_files)
            f.write(
                f"{p.identifier},{p.files_touched},{p.loc_added},"
                f"{p.ai_debt_delta:.3f},{p.ai_risk_index:.3f},{top}\n"
            )

    return reports_dir


def render_html(
    root: Path,
    reports_dir: Path,
    files: List[FileMetrics],
    buckets: List[TimeBucketMetrics],
    prs: List[PRMetrics],
):
    html_path = reports_dir / "report.html"
    root = root.resolve()

    # ------------------------------------------------------------------
    # Module heatmap: group by first 1–2 components of *relative* path
    # ------------------------------------------------------------------
    module_scores = {}
    file_rows = []

    for fm in files:
        # Normalize to path relative to repo root
        try:
            rel_path = Path(fm.path).resolve().relative_to(root)
            norm_path = str(rel_path).replace("\\", "/")
        except ValueError:
            norm_path = Path(fm.path).name

        parts = norm_path.split("/")
        if len(parts) >= 2:
            module = "/".join(parts[:2])
        elif parts:
            module = parts[0]
        else:
            module = "(root)"

        info = module_scores.setdefault(module, {"sum": 0.0, "count": 0})
        info["sum"] += fm.ai_debt_score
        info["count"] += 1

        s = fm.smell
        file_rows.append(
            {
                "path": norm_path,
                "module": module,
                "loc": fm.loc,
                "ai_debt": fm.ai_debt_score,
                "ai_influence": fm.ai_influence,
                "dup": s.duplicate_blocks,
                "api": s.api_hallucinations,
                "over_eng": s.over_engineering,
                "unnecessary_abs": s.unnecessary_abstractions,
                "silent": s.silent_failures,
            }
        )

    modules = list(module_scores.keys())
    module_values = [module_scores[m]["sum"] / max(1, module_scores[m]["count"]) for m in modules]

    # ------------------------------------------------------------------
    # Time trend
    # ------------------------------------------------------------------
    buckets_sorted = sorted(buckets, key=lambda b: b.bucket)
    bucket_labels = [b.bucket for b in buckets_sorted]
    bucket_debt = [b.ai_debt_avg for b in buckets_sorted]

    # ------------------------------------------------------------------
    # PR risk
    # ------------------------------------------------------------------
    prs_sorted = sorted(prs, key=lambda p: p.ai_risk_index, reverse=True)
    pr_ids = [p.identifier for p in prs_sorted]
    pr_risks = [p.ai_risk_index for p in prs_sorted]

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------
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
    .detail {{ width: 100%; max-width: 1000px; margin-top: 10px; margin-bottom: 40px; }}
    .detail-table {{ border-collapse: collapse; width: 100%; }}
    .detail-table th, .detail-table td {{
      border: 1px solid #ddd;
      padding: 6px 8px;
      font-size: 12px;
      text-align: left;
    }}
    .detail-table th {{
      background: #f5f5f5;
      font-weight: 600;
    }}
    .detail-table tr.high-risk {{ background-color: #ffe5e5; }}
    .detail-table tr.mid-risk {{ background-color: #fff4e0; }}
    .detail-table tr.low-risk {{ background-color: #f8f8f8; }}
  </style>
</head>
<body>
  <h1>AI 技术债热力图 & 趋势</h1>

  <h2>模块 AI 技术债分布（热力图）</h2>
  <div id="heatmap" class="chart"></div>
  <div id="module-detail" class="detail">
    <p>💡 点击上面的任意模块，可以查看该模块内部 AI 债务最高的 Top 10 文件。</p>
  </div>

  <h2>AI 债务趋势（按时间）</h2>
  <div id="timeline" class="chart"></div>

  <h2>PR 风险指数 Top</h2>
  <div id="prrisk" class="chart"></div>

  <script>
    // Data injected from Python
    var modules = {json.dumps(modules)};
    var moduleValues = {json.dumps(module_values)};
    var filesData = {json.dumps(file_rows)};
    var bucketLabels = {json.dumps(bucket_labels)};
    var bucketDebt = {json.dumps(bucket_debt)};
    var prIds = {json.dumps(pr_ids)};
    var prRisks = {json.dumps(pr_risks)};

    // Heatmap
    var heatData = [{{
      x: modules,
      y: ["AI Debt"],
      z: [moduleValues],
      type: 'heatmap',
      colorscale: 'Reds',
      hovertemplate: "模块: {{x}}<br>平均 AI 债务: {{z:.2f}}<extra></extra>"
    }}];

    var heatLayout = {{
      title: 'Module AI Tech Debt Heatmap',
      xaxis: {{ automargin: true }},
      yaxis: {{ automargin: true }}
    }};

    Plotly.newPlot('heatmap', heatData, heatLayout);

    // Drill-down
    function renderModuleDetail(moduleName) {{
      var container = document.getElementById('module-detail');

      var rows = filesData.filter(function (f) {{
        return f.module === moduleName;
      }});

      if (!rows.length) {{
        container.innerHTML = "<h3>模块 " + moduleName + "</h3><p>未找到文件。</p>";
        return;
      }}

      rows.sort(function (a, b) {{
        return b.ai_debt - a.ai_debt;
      }});

      var top = rows.slice(0, 10);

      var dupSum = 0, apiSum = 0, overSum = 0, absSum = 0, silentSum = 0, avgDebt = 0;
      top.forEach(function (r) {{
        dupSum += r.dup;
        apiSum += r.api;
        overSum += r.over_eng;
        absSum += r.unnecessary_abs;
        silentSum += r.silent;
        avgDebt += r.ai_debt;
      }});
      avgDebt = avgDebt / top.length;

      var summary = `
        <h3>模块 ${'{'}moduleName{'}'} · Top 10 AI 债务文件</h3>
        <p>
          综合评语：该模块在 Top 10 文件中，共检测到
          <b>${'{'}dupSum{'}'}</b> 次重复代码，
          <b>${'{'}silentSum{'}'}</b> 个 silent failure，
          <b>${'{'}overSum{'}'}</b> 个过度工程 wrapper，
          <b>${'{'}absSum{'}'}</b> 个不必要抽象，
          <b>${'{'}apiSum{'}'}</b> 个 API 幻觉。
          平均 AI 债务分数约为 <b>${'{'}avgDebt.toFixed(2){'}'}</b>。
          这些特征非常符合“AI 放大技术债”的典型模式。
        </p>
      `;

      var tableRows = top.map(function (r, idx) {{
        var riskClass = "low-risk";
        var riskLabel = "";
        if (r.ai_debt > 0.8) {{
          riskClass = "high-risk";
          riskLabel = "🔥 AI 屎山候选";
        }} else if (r.ai_debt > 0.6) {{
          riskClass = "mid-risk";
          riskLabel = "⚠ 需要关注";
        }}

        return `
          <tr class="${'{'}riskClass{'}'}">
            <td>${'{'}idx + 1{'}'}</td>
            <td>${'{'}r.path{'}'}</td>
            <td>${'{'}r.ai_debt.toFixed(2){'}'}</td>
            <td>${'{'}riskLabel{'}'}</td>
            <td>${'{'}r.dup{'}'}</td>
            <td>${'{'}r.api{'}'}</td>
            <td>${'{'}r.over_eng{'}'}</td>
            <td>${'{'}r.unnecessary_abs{'}'}</td>
            <td>${'{'}r.silent{'}'}</td>
          </tr>
        `;
      }}).join("");

      var tableHtml = `
        ${'{'}summary{'}'}
        <table class="detail-table">
          <thead>
            <tr>
              <th>#</th>
              <th>File</th>
              <th>AI Debt</th>
              <th>标记</th>
              <th>重复</th>
              <th>API 幻觉</th>
              <th>过度工程</th>
              <th>不必要抽象</th>
              <th>Silent Failure</th>
            </tr>
          </thead>
          <tbody>
            ${'{'}tableRows{'}'}
          </tbody>
        </table>
      `;

      container.innerHTML = tableHtml;
    }}

    var heatDiv = document.getElementById('heatmap');
    heatDiv.on('plotly_click', function(data) {{
      if (data.points && data.points.length > 0) {{
        var moduleName = data.points[0].x;
        renderModuleDetail(moduleName);
      }}
    }});

    if (modules.length > 0) {{
      renderModuleDetail(modules[0]);
    }}

    // Timeline
    var tlData = [{{
      x: bucketLabels,
      y: bucketDebt,
      type: 'scatter',
      mode: 'lines+markers'
    }}];

    Plotly.newPlot('timeline', tlData, {{title: 'AI Debt Trend Over Time'}});

    // PR risk
    var prData = [{{
      x: prIds,
      y: prRisks,
      type: 'bar'
    }}];

    Plotly.newPlot('prrisk', prData, {{title: 'PR Risk Index'}});
  </script>
</body>
</html>
"""
        )

    return html_path
