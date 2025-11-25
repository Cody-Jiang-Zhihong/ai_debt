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

    # timeline.csv — cumulative AI debt
    with (reports_dir / "timeline.csv").open("w", encoding="utf-8") as f:
        f.write("bucket,ai_debt_sum,ai_debt_avg,commits\n")
        for b in buckets:
            f.write(f"{b.bucket},{b.ai_debt_sum:.3f},{b.ai_debt_avg:.3f},{b.commits}\n")

    # timeline_monthly.csv — per-month new AI debt (non-cumulative)
    buckets_sorted = sorted(buckets, key=lambda b: b.bucket)
    prev_sum = 0.0
    with (reports_dir / "timeline_monthly.csv").open("w", encoding="utf-8") as f:
        f.write("bucket,ai_debt_delta,commits\n")
        for b in buckets_sorted:
            delta = b.ai_debt_sum - prev_sum
            prev_sum = b.ai_debt_sum
            f.write(f"{b.bucket},{delta:.3f},{b.commits}\n")

    # prs.csv
    with (reports_dir / "prs.csv").open("w", encoding="utf-8") as f:
        f.write("id,files_touched,loc_added,ai_debt_delta,ai_risk_index,semantic_drift,top_files\n")
        for p in prs:
            top = ";".join(p.top_files)
            f.write(
                f"{p.identifier},{p.files_touched},{p.loc_added},"
                f"{p.ai_debt_delta:.3f},{p.ai_risk_index:.3f},"
                f"{p.semantic_drift:.3f},{top}\n"
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
    # Module heatmap  —— 简化 & 稳定：按顶层目录分组
    # ------------------------------------------------------------------
    module_scores = {}
    file_rows = []

    for fm in files:
        # fm.path 通常是 repo 内的相对路径
        path = str(fm.path).replace("\\", "/").lstrip("./")
        parts = path.split("/")

        if len(parts) > 1:
            module = parts[0]        # 顶层文件夹：比如 "thefuck", "tests"
        else:
            module = parts[0]        # 根目录文件：比如 "setup.py"

        s = fm.smell

        info = module_scores.setdefault(module, {"sum": 0.0, "count": 0})
        info["sum"] += fm.ai_debt_score
        info["count"] += 1

        file_rows.append(
            {
                "path": path,
                "module": module,
                "loc": fm.loc,
                "ai_influence": fm.ai_influence,
                "ai_debt": fm.ai_debt_score,
                "dup": s.duplicate_blocks,
                "api": s.api_hallucinations,
                "over_eng": s.over_engineering,
                "unnecessary_abs": s.unnecessary_abstractions,
                "silent": s.silent_failures,
                "recent_added": fm.recent_added,
            }
        )

    modules = list(module_scores.keys())
    module_values = [
        module_scores[m]["sum"] / max(1, module_scores[m]["count"])
        for m in modules
    ]

    # ------------------------------------------------------------------
    # Time trend
    # ------------------------------------------------------------------
    buckets_sorted = sorted(buckets, key=lambda b: b.bucket)
    bucket_labels = [b.bucket for b in buckets_sorted]
    bucket_debt = [b.ai_debt_sum for b in buckets_sorted]

    # Per-month new AI debt (non-cumulative)
    bucket_delta = []
    prev_sum = 0.0
    for b in buckets_sorted:
        delta = b.ai_debt_sum - prev_sum
        bucket_delta.append(delta)
        prev_sum = b.ai_debt_sum

    # ------------------------------------------------------------------
    # PR risk
    # ------------------------------------------------------------------
    prs_sorted = sorted(prs, key=lambda p: p.ai_risk_index, reverse=True)
    pr_ids = [p.identifier for p in prs_sorted]
    pr_risks = [p.ai_risk_index for p in prs_sorted]
    pr_drifts = [p.semantic_drift for p in prs_sorted]

    # ------------------------------------------------------------------
    # HTML / JS
    # ------------------------------------------------------------------
    modules_js = json.dumps(modules)
    module_values_js = json.dumps(module_values)
    filesdata_js = json.dumps(file_rows)
    bucket_labels_js = json.dumps(bucket_labels)
    bucket_debt_js = json.dumps(bucket_debt)
    bucket_delta_js = json.dumps(bucket_delta)
    pr_ids_js = json.dumps(pr_ids)
    pr_risks_js = json.dumps(pr_risks)
    pr_drifts_js = json.dumps(pr_drifts)

    with html_path.open("w", encoding="utf-8") as f:
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            "  <title>AI Tech Debt Report</title>\n"
            "  <script src=\"https://cdn.plot.ly/plotly-latest.min.js\"></script>\n"
            "  <style>\n"
            "    body { font-family: sans-serif; margin: 20px; }\n"
            "    .chart { width: 100%; max-width: 1000px; height: 400px; margin-bottom: 40px; }\n"
            "    .detail { width: 100%; max-width: 1000px; margin-top: 10px; margin-bottom: 40px; }\n"
            "    .detail-table { border-collapse: collapse; width: 100%; }\n"
            "    .detail-table th, .detail-table td {\n"
            "      border: 1px solid #ddd;\n"
            "      padding: 6px 8px;\n"
            "      font-size: 12px;\n"
            "      text-align: left;\n"
            "    }\n"
            "    .detail-table th {\n"
            "      background: #f5f5f5;\n"
            "      font-weight: 600;\n"
            "    }\n"
            "    .detail-table tr.high-risk { background-color: #ffe5e5; }\n"
            "    .detail-table tr.mid-risk { background-color: #fff4e0; }\n"
            "    .detail-table tr.low-risk { background-color: #f8f8f8; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <h1>AI Tech Debt Heatmap & Trend</h1>\n\n"
            "  <h2>Module AI Debt Distribution (Heatmap)</h2>\n"
            "  <div id=\"heatmap\" class=\"chart\"></div>\n"
            "  <div id=\"module-detail\" class=\"detail\">\n"
            "    <p>💡 Click any module above to see its top 10 highest-debt files.</p>\n"
            "  </div>\n\n"
            "  <h2>AI Debt Trend Over Time</h2>\n"
            "  <div id=\"timeline-toggle\" style=\"margin-bottom: 8px;\">\n"
            "    <label><input type=\"radio\" name=\"timelineMode\" value=\"cumulative\" checked> Cumulative</label>\n"
            "    <label style=\"margin-left: 12px;\"><input type=\"radio\" name=\"timelineMode\" value=\"monthly\"> Monthly new</label>\n"
            "  </div>\n"
            "  <div id=\"timeline\" class=\"chart\"></div>\n\n"
            "  <h2>PR Risk Index (Top)</h2>\n"
            "  <div id=\"prrisk\" class=\"chart\"></div>\n\n"
            "  <script>\n"
            "    // Data injected from Python\n"
            "    var modules = " + modules_js + ";\n"
            "    var moduleValues = " + module_values_js + ";\n"
            "    var filesData = " + filesdata_js + ";\n"
            "    var bucketLabels = " + bucket_labels_js + ";\n"
            "    var bucketDebt = " + bucket_debt_js + ";\n"
            "    var bucketDelta = " + bucket_delta_js + ";\n"
            "    var prIds = " + pr_ids_js + ";\n"
            "    var prRisks = " + pr_risks_js + ";\n"
            "    var prDrifts = " + pr_drifts_js + ";\n\n"
            "    // Heatmap\n"
            "    var heatData = [{\n"
            "      x: modules,\n"
            "      y: ['AI Debt'],\n"
            "      z: [moduleValues],\n"  # 1 row, N columns
            "      type: 'heatmap',\n"
            "      colorscale: 'Reds',\n"
            "      hovertemplate: 'Module: %{x}<br>Avg AI debt: %{z:.3f}<extra></extra>'\n"
            "    }];\n\n"
            "    var heatLayout = {\n"
            "      title: 'Module AI Tech Debt Heatmap',\n"
            "      xaxis: { automargin: true },\n"
            "      yaxis: { automargin: true }\n"
            "    };\n\n"
            "    Plotly.newPlot('heatmap', heatData, heatLayout);\n\n"
            "    // Drill-down\n"
            "    function renderModuleDetail(moduleName) {\n"
            "      var container = document.getElementById('module-detail');\n"
            "      var rows = filesData.filter(function (f) {\n"
            "        return f.module === moduleName;\n"
            "      });\n"
            "      if (!rows.length) {\n"
            "        container.innerHTML = '<h3>Module ' + moduleName + '</h3><p>No files found.</p>';\n"
            "        return;\n"
            "      }\n"
            "      rows.sort(function (a, b) { return b.ai_debt - a.ai_debt; });\n"
            "      var top = rows.slice(0, 10);\n"
            "      var dupSum = 0, apiSum = 0, overSum = 0, absSum = 0, silentSum = 0, avgDebt = 0;\n"
            "      top.forEach(function (r) {\n"
            "        dupSum += r.dup;\n"
            "        apiSum += r.api;\n"
            "        overSum += r.over_eng;\n"
            "        absSum += r.unnecessary_abs;\n"
            "        silentSum += r.silent;\n"
            "        avgDebt += r.ai_debt;\n"
            "      });\n"
            "      avgDebt = avgDebt / top.length;\n"
            "      var summary = `\n"
            "        <h3>Module ${moduleName} · Top 10 Debt Files</h3>\n"
            "        <p>\n"
            "          Overall Evaluation - This module detected: \n"
            "          <b>${dupSum}</b> Duplicate blocks，\n"
            "          <b>${silentSum}</b> 个 silent failure，\n"
            "          <b>${overSum}</b> Over-engineering wrappers，\n"
            "          <b>${absSum}</b> Unnecessary abstractions，\n"
            "          <b>${apiSum}</b> API hallucinations.\n"
            "          Avg AI debt score <b>${avgDebt.toFixed(2)}</b>。\n"
            "        </p>\n"
            "      `;\n"
            "      var tableRows = top.map(function (r, idx) {\n"
            "        var riskClass = 'low-risk';\n"
            "        var riskLabel = '';\n"
            "        if (r.ai_debt > 0.8) { riskClass = 'high-risk'; riskLabel = '🔥 AI High Risk'; }\n"
            "        else if (r.ai_debt > 0.6) { riskClass = 'mid-risk'; riskLabel = '⚠ Moderate Risk'; }\n"
            "        return `\n"
            "          <tr class='${riskClass}'>\n"
            "            <td>${idx + 1}</td>\n"
            "            <td>${r.path}</td>\n"
            "            <td>${r.loc}</td>\n"
            "            <td>${r.ai_influence.toFixed(2)}</td>\n"
            "            <td>${r.ai_debt.toFixed(2)} ${riskLabel}</td>\n"
            "            <td>${r.dup}</td>\n"
            "            <td>${r.api}</td>\n"
            "            <td>${r.over_eng}</td>\n"
            "            <td>${r.unnecessary_abs}</td>\n"
            "            <td>${r.silent}</td>\n"
            "          </tr>`;\n"
            "      }).join('\\n');\n"
            "      var tableHtml = `\n"
            "        ${summary}\n"
            "        <table class='detail-table'>\n"
            "          <thead>\n"
            "            <tr>\n"
            "              <th>#</th>\n"
            "              <th>File</th>\n"
            "              <th>LOC</th>\n"
            "              <th>AI Influence</th>\n"
            "              <th>AI Debt</th>\n"
            "              <th>Duplicate Blocks</th>\n"
            "              <th>API Hallucinations</th>\n"
            "              <th>Over-Engineering</th>\n"
            "              <th>Unnecessary Abstraction</th>\n"
            "              <th>Silent Failure</th>\n"
            "            </tr>\n"
            "          </thead>\n"
            "          <tbody>\n"
            "            ${tableRows}\n"
            "          </tbody>\n"
            "        </table>`;\n"
            "      container.innerHTML = tableHtml;\n"
            "    }\n"
            "    var heatDiv = document.getElementById('heatmap');\n"
            "    heatDiv.on('plotly_click', function(data) {\n"
            "      if (data.points && data.points.length > 0) {\n"
            "        var moduleName = data.points[0].x;\n"
            "        renderModuleDetail(moduleName);\n"
            "      }\n"
            "    });\n"
            "    if (modules.length > 0) { renderModuleDetail(modules[0]); }\n\n"
            "    // Timeline\n"
            "    var tlData = [\n"
            "      { x: bucketLabels, y: bucketDebt, type: 'scatter', mode: 'lines+markers', name: 'Cumulative AI debt' },\n"
            "      { x: bucketLabels, y: bucketDelta, type: 'bar', name: 'Monthly new AI debt' }\n"
            "    ];\n"
            "    Plotly.newPlot('timeline', tlData, { title: 'AI Debt Trend Over Time' });\n"
            "    function setTimelineMode(mode) {\n"
            "      if (mode === 'cumulative') {\n"
            "        Plotly.restyle('timeline', {visible: [true, false]});\n"
            "      } else {\n"
            "        Plotly.restyle('timeline', {visible: [false, true]});\n"
            "      }\n"
            "    }\n"
            "    setTimelineMode('cumulative');\n"
            "    var radios = document.getElementsByName('timelineMode');\n"
            "    for (var i = 0; i < radios.length; i++) {\n"
            "      radios[i].addEventListener('change', function (e) { setTimelineMode(e.target.value); });\n"
            "    }\n\n"
            "    // PR Risk\n"
            "    var prData = [{\n"
            "      x: prIds,\n"
            "      y: prRisks,\n"
            "      type: 'bar',\n"
            "      customdata: prDrifts,\n"
            "      marker: {\n"
            "        color: prDrifts,\n"
            "        colorscale: 'RdBu',\n"
            "        reversescale: true,\n"
            "        cmin: 0,\n"
            "        cmax: 1,\n"
            "        colorbar: { title: 'Semantic Drift' }\n"
            "      },\n"
            "      hovertemplate: 'PR: %{x}<br>Risk: %{y:.2f}<br>Semantic drift: %{customdata:.2f}<extra></extra>'\n"
            "    }];\n"
            "    Plotly.newPlot('prrisk', prData, { title: 'PR Risk Index (Semantic Drift Colored)' });\n"
            "  </script>\n"
            "</body>\n"
            "</html>\n"
        )
        f.write(html)

    return html_path
