export const emptyTune = {
  backend: 'color',
  color: { hue_min: 0, hue_max: 10, saturation_min: 120, value_min: 80 },
  control: { kp: 0.12, ki: 0, kd: 0.01 },
}

export function fmt(value: number | undefined | null, digits = 1): string {
  return value == null || Number.isNaN(value) ? '--' : value.toFixed(digits)
}

export function isTypingTarget(el: Element | null): boolean {
  if (!el) return false
  const tag = el.tagName
  return ['INPUT', 'SELECT', 'TEXTAREA'].includes(tag) || (el as HTMLElement).isContentEditable
}

export function clone<T>(value: T): T {
  return structuredClone(value)
}
