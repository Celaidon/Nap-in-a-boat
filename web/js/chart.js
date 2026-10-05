/**
 * web/js/chart.js
 * Capability Curve visualization powered by Chart.js.
 * 
 * Plots:
 * 1. Sweep points (sweep_000 to sweep_100) along t=0..1
 *    - Code Pass Rate % (Left Y-axis)
 *    - Writing Style Score 1..10 (Right Y-axis)
 * 2. Special non-sweep variants (split_attn_code, split_mlp_code, gradient_mid) as scatter points at t=0.5
 * 3. Highlights the currently selected blend.
 */

let capabilityChart = null;

const SWEEP_IDS = ["sweep_000", "sweep_025", "sweep_050", "sweep_075", "sweep_100"];

/**
 * Renders or updates the capability curve chart.
 * @param {Object} metrics - Data from GET /api/metrics
 * @param {Object} registry - Data from GET /api/registry
 * @param {string} [activeBlendId="sweep_050"] - Selected blend ID to highlight
 */
export function renderCapabilityCurve(metrics, registry, activeBlendId = "sweep_050") {
  const canvas = document.getElementById("capabilityChart");
  if (!canvas) {
    console.warn("Chart canvas '#capabilityChart' not found.");
    return;
  }

  const blendsMap = new Map();
  if (metrics && Array.isArray(metrics.blends)) {
    metrics.blends.forEach((b) => blendsMap.set(b.blend_id, b));
  }

  const registryMap = new Map();
  if (registry && Array.isArray(registry.blends)) {
    registry.blends.forEach((b) => registryMap.set(b.id, b));
  }

  // Extract sweep data points
  const sweepData = SWEEP_IDS.map((id) => {
    const reg = registryMap.get(id) || {};
    const met = blendsMap.get(id) || {};
    return {
      id,
      t: reg.t ?? 0,
      codePass: (met.code_pass ?? 0) * 100, // percentage
      styleScore: met.style_score ?? 0,
    };
  });

  // Extract special variant points
  const specialIds = ["split_attn_code", "split_mlp_code", "gradient_mid"];
  const specialDataCode = [];
  const specialDataStyle = [];

  specialIds.forEach((id) => {
    const reg = registryMap.get(id) || {};
    const met = blendsMap.get(id) || {};
    const tVal = reg.t ?? 0.5;
    const label = reg.label || id;

    if (met.code_pass !== undefined) {
      specialDataCode.push({
        x: tVal,
        y: met.code_pass * 100,
        id,
        label: `${label} (Code)`,
      });
    }
    if (met.style_score !== undefined) {
      specialDataStyle.push({
        x: tVal,
        y: met.style_score,
        id,
        label: `${label} (Style)`,
      });
    }
  });

  // Calculate highlight radius/point sizes based on activeBlendId
  const getPointRadius = (ctx) => {
    const item = ctx.raw;
    if (item && item.id === activeBlendId) return 10;
    return 5;
  };

  const getPointHoverRadius = (ctx) => {
    const item = ctx.raw;
    if (item && item.id === activeBlendId) return 12;
    return 8;
  };

  const chartData = {
    labels: sweepData.map((d) => `t=${d.t}`),
    datasets: [
      {
        label: "Coding Pass Rate (%)",
        data: sweepData.map((d) => ({ x: d.t, y: d.codePass, id: d.id })),
        borderColor: "#3b82f6", // Blue
        backgroundColor: "rgba(59, 130, 246, 0.15)",
        yAxisID: "yCode",
        tension: 0.3,
        fill: true,
        pointRadius: getPointRadius,
        pointHoverRadius: getPointHoverRadius,
        pointBackgroundColor: sweepData.map((d) => (d.id === activeBlendId ? "#ef4444" : "#3b82f6")),
      },
      {
        label: "Writing Style Score (1-10)",
        data: sweepData.map((d) => ({ x: d.t, y: d.styleScore, id: d.id })),
        borderColor: "#10b981", // Emerald Green
        backgroundColor: "rgba(16, 185, 129, 0.15)",
        yAxisID: "yStyle",
        tension: 0.3,
        fill: true,
        pointRadius: getPointRadius,
        pointHoverRadius: getPointHoverRadius,
        pointBackgroundColor: sweepData.map((d) => (d.id === activeBlendId ? "#ef4444" : "#10b981")),
      },
      {
        label: "Special Variants (Code)",
        data: specialDataCode,
        borderColor: "#8b5cf6", // Purple
        backgroundColor: "#8b5cf6",
        pointStyle: "rectRot",
        pointRadius: (ctx) => (ctx.raw?.id === activeBlendId ? 11 : 7),
        yAxisID: "yCode",
        showLine: false,
      },
      {
        label: "Special Variants (Style)",
        data: specialDataStyle,
        borderColor: "#f59e0b", // Amber
        backgroundColor: "#f59e0b",
        pointStyle: "triangle",
        pointRadius: (ctx) => (ctx.raw?.id === activeBlendId ? 11 : 7),
        yAxisID: "yStyle",
        showLine: false,
      },
    ],
  };

  const chartConfig = {
    type: "line",
    data: chartData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "nearest",
        intersect: false,
      },
      plugins: {
        legend: {
          position: "top",
          labels: {
            font: { family: "Inter, sans-serif", size: 12 },
            usePointStyle: true,
          },
        },
        tooltip: {
          callbacks: {
            title: (items) => {
              const item = items[0];
              if (item && item.raw && item.raw.id) {
                return `Blend: ${item.raw.id}`;
              }
              return items[0].label;
            },
            label: (context) => {
              const unit = context.dataset.yAxisID === "yCode" ? "%" : "/10";
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}${unit}`;
            },
          },
        },
      },
      scales: {
        x: {
          type: "linear",
          min: 0,
          max: 1.0,
          title: {
            display: true,
            text: "Blend Ratio t (0 = Model A / Writing, 1 = Model B / Code)",
            font: { weight: "bold" },
          },
          ticks: {
            stepSize: 0.25,
            callback: (val) => `t=${val}`,
          },
        },
        yCode: {
          type: "linear",
          position: "left",
          min: 0,
          max: 100,
          title: {
            display: true,
            text: "Code Pass Rate (%)",
            color: "#3b82f6",
            font: { weight: "bold" },
          },
          grid: { drawOnChartArea: true },
        },
        yStyle: {
          type: "linear",
          position: "right",
          min: 0,
          max: 10,
          title: {
            display: true,
            text: "Writing Style Score (1-10)",
            color: "#10b981",
            font: { weight: "bold" },
          },
          grid: { drawOnChartArea: false }, // avoid overlapping grid lines
        },
      },
    },
  };

  if (capabilityChart) {
    capabilityChart.destroy();
  }

  // Ensure Chart.js is available globally (e.g. loaded via CDN in index.html)
  if (typeof window.Chart !== "undefined") {
    capabilityChart = new window.Chart(canvas, chartConfig);
  } else {
    console.error("Chart.js library not loaded in window.Chart");
  }
}
