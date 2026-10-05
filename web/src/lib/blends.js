// Helpers for reading the registry.
export const VARIANT_ORDER = ['split_attn_code', 'split_mlp_code', 'gradient_mid']

export const VARIANT_INFO = {
  split_attn_code: { name: 'Attention to code', hint: 'Attention layers mostly from the code model, MLP from the writing model' },
  split_mlp_code: { name: 'MLP to code', hint: 'MLP layers mostly from the code model, attention from the writing model' },
  gradient_mid: { name: 'Gradient', hint: 'Code influence peaks in the middle layers' },
}

/** The uniform blends, left (writing) to right (code). They sit on the slider. */
export const sweepStops = (blends) => blends.filter((b) => b.variant === 'uniform').sort((a, b) => a.t - b.t)

export const variantBlends = (blends) =>
  VARIANT_ORDER.map((v) => blends.find((b) => b.variant === v)).filter(Boolean)

export const findBlend = (blends, id) => blends.find((b) => b.id === id)

export const percent = (t) => `${Math.round(t * 100)}%`

export function describeBlend(blend) {
  if (!blend) return ''
  if (blend.variant !== 'uniform') return VARIANT_INFO[blend.variant]?.name ?? blend.label
  if (blend.t === 0) return 'Writing model'
  if (blend.t === 1) return 'Code model'
  return `${percent(blend.t)} code`
}

export const metricsFor = (metrics, id) => metrics?.blends.find((m) => m.blend_id === id)
