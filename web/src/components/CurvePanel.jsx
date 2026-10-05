// Capability curve: code pass rate and style score for every blend, from results/metrics.json.
// A vertical marker follows the slider. Every number shown comes straight from the metrics file.
import { animate } from 'framer-motion'
import { Chart as ChartJS, Filler, LineElement, LinearScale, PointElement, Tooltip } from 'chart.js'
import { useEffect, useMemo, useRef } from 'react'
import { Scatter } from 'react-chartjs-2'
import { VARIANT_INFO, describeBlend, findBlend, metricsFor, sweepStops, variantBlends } from '../lib/blends.js'

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Filler)

const CODE = '#6b0011'
const STYLE = '#b87812'
const INK = '#2b0409'
const GRID = '#efd2d5'
// The three variants all sit at t = 0.5, so they are drawn slightly apart to stay visible.
const NUDGE = { split_attn_code: -0.045, split_mlp_code: 0, gradient_mid: 0.045 }
const SHAPE = { split_attn_code: 'triangle', split_mlp_code: 'rect', gradient_mid: 'rectRot' }

const markerPlugin = {
  id: 'marker',
  afterDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea, scales } = chart
    const t = opts.ref?.current
    if (t == null) return
    const x = scales.x.getPixelForValue(t)
    ctx.save()
    ctx.strokeStyle = INK
    ctx.lineWidth = 2
    ctx.setLineDash([2, 5])
    ctx.beginPath()
    ctx.moveTo(x, chartArea.top)
    ctx.lineTo(x, chartArea.bottom)
    ctx.stroke()
    ctx.restore()
  },
}

export function CurvePanel({ blends, metrics, blendId }) {
  const chartRef = useRef(null)
  const markerRef = useRef(findBlend(blends, blendId)?.t ?? 0.5)
  const selected = findBlend(blends, blendId)

  // Glide the marker to the new slider position.
  useEffect(() => {
    if (!selected) return
    const controls = animate(markerRef.current, selected.t, {
      duration: 0.45, ease: [0.22, 0.8, 0.28, 1],
      onUpdate: (v) => {
        markerRef.current = v
        chartRef.current?.draw()
      },
    })
    return () => controls.stop()
  }, [selected])

  const { data, options } = useMemo(() => {
    const point = (blend, key, scale, jitter = 0) => {
      const m = metricsFor(metrics, blend.id)
      return m ? { x: blend.t + jitter, y: m[key] * scale, id: blend.id } : null
    }
    const sweep = sweepStops(blends)
    const variants = variantBlends(blends)
    const isSelected = (ctx) => ctx.raw?.id === blendId
    const dots = (color) => ({
      borderColor: color, backgroundColor: color, pointRadius: (c) => (isSelected(c) ? 8 : 5),
      pointHoverRadius: 8, pointBorderColor: INK, pointBorderWidth: (c) => (isSelected(c) ? 2.5 : 0),
    })

    const datasets = [
      { label: 'Code pass', yAxisID: 'code', showLine: true, tension: 0.25, borderWidth: 3, ...dots(CODE),
        data: sweep.map((b) => point(b, 'code_pass', 100)).filter(Boolean) },
      { label: 'Style score', yAxisID: 'style', showLine: true, tension: 0.25, borderWidth: 3, ...dots(STYLE),
        data: sweep.map((b) => point(b, 'style_score', 1)).filter(Boolean) },
      { label: 'Code pass (variants)', yAxisID: 'code', showLine: false, ...dots(CODE),
        pointStyle: variants.map((v) => SHAPE[v.variant]), pointRadius: (c) => (isSelected(c) ? 10 : 7),
        data: variants.map((v) => point(v, 'code_pass', 100, NUDGE[v.variant])).filter(Boolean) },
      { label: 'Style score (variants)', yAxisID: 'style', showLine: false, ...dots(STYLE),
        pointStyle: variants.map((v) => SHAPE[v.variant]), pointRadius: (c) => (isSelected(c) ? 10 : 7),
        data: variants.map((v) => point(v, 'style_score', 1, NUDGE[v.variant])).filter(Boolean) },
    ]
    const ref = metrics?.reference
    if (ref) {
      const line = (label, axis, y, color) => ({
        label, yAxisID: axis, showLine: true, borderDash: [7, 6], borderWidth: 2, borderColor: color,
        pointRadius: 0, pointHoverRadius: 0, data: [{ x: 0, y }, { x: 1, y }],
      })
      datasets.push(line(`${ref.name} (code)`, 'code', ref.code_pass * 100, `${CODE}99`))
      datasets.push(line(`${ref.name} (style)`, 'style', ref.style_score, `${STYLE}99`))
    }

    const axis = (title, color, extra) => ({
      title: { display: true, text: title, color, font: { family: 'DM Sans', weight: '700', size: 12 } },
      ticks: { color: INK, font: { family: 'DM Sans', size: 11 } }, border: { color: INK, width: 2 }, ...extra,
    })
    return {
      data: { datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 650, easing: 'easeOutQuart' },
        interaction: { mode: 'nearest', intersect: true },
        scales: {
          x: { type: 'linear', min: -0.04, max: 1.04, grid: { color: GRID },
            title: { display: true, text: 'Writing model  →  Code model', color: INK, font: { family: 'DM Sans', weight: '700', size: 12 } },
            afterBuildTicks: (scale) => { scale.ticks = [0, 0.25, 0.5, 0.75, 1].map((value) => ({ value })) },
            ticks: { color: INK, font: { family: 'DM Sans', size: 11 }, callback: (v) => `${Math.round(v * 100)}%` },
            border: { color: INK, width: 2 } },
          code: axis('Code pass %', CODE, { position: 'left', min: 0, max: 100, grid: { color: GRID } }),
          style: axis('Style score /10', STYLE, { position: 'right', min: 0, max: 10, grid: { drawOnChartArea: false } }),
        },
        plugins: {
          legend: { display: false },
          marker: { ref: markerRef },
          tooltip: {
            backgroundColor: INK, titleFont: { family: 'DM Sans', weight: '700' }, bodyFont: { family: 'DM Sans' }, padding: 10, cornerRadius: 8,
            filter: (item) => item.raw?.id,
            callbacks: {
              title: (items) => { const b = findBlend(blends, items[0].raw.id); return b ? `${describeBlend(b)} (${b.id})` : '' },
              label: (item) => (item.dataset.yAxisID === 'code' ? `Code pass ${item.raw.y.toFixed(0)}%` : `Style ${item.raw.y.toFixed(1)} / 10`),
            },
          },
        },
      },
    }
  }, [blends, metrics, blendId])

  const m = metricsFor(metrics, blendId)
  const reference = metrics?.reference

  return (
    <div className="curve">
      <div className="curve-chart">
        <Scatter ref={chartRef} data={data} options={options} plugins={[markerPlugin]} />
      </div>

      <ul className="legend">
        <li><i className="key key-code" /> Code pass</li>
        <li><i className="key key-style" /> Style score</li>
        {variantBlends(blends).map((v) => (
          <li key={v.id}><i className={`key key-shape key-${SHAPE[v.variant]}`} /> {VARIANT_INFO[v.variant]?.name}</li>
        ))}
        {reference && <li><i className="key key-dash" /> {reference.name}</li>}
      </ul>

      {selected && m && (
        <div className="readout">
          <strong>{describeBlend(selected)}</strong> <span className="mono">{selected.id}</span>
          <dl>
            <div><dt>Code pass</dt><dd>{(m.code_pass * 100).toFixed(0)}%</dd></div>
            <div><dt>Style</dt><dd>{m.style_score.toFixed(1)} <small>±{m.style_score_std.toFixed(1)}</small></dd></div>
            <div><dt>Rhyme</dt><dd>{(m.rhyme_score * 100).toFixed(0)}%</dd></div>
            <div><dt>Speed</dt><dd>{m.tokens_per_sec.toFixed(1)} <small>tok/s</small></dd></div>
          </dl>
        </div>
      )}

      <p className="note">
        Measured on {metrics?.n_code} coding problems and {metrics?.n_style} writing prompts, style judged by {metrics?.judge_model}.
        The three variants are all at 50% and are drawn slightly apart so they do not overlap. Mid-range blends can produce odd text; the numbers show it.
      </p>
    </div>
  )
}
