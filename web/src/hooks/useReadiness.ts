import type { Health, Telemetry } from '../types/prahari'

export type ReadinessItem = {
  id: string
  label: string
  ok: boolean
  state: string
  detail: string
  tone: 'ok' | 'warn' | 'bad' | 'neutral'
}

export function useReadiness(health: Health | null, telemetry: Telemetry | null, link: string) {
  const hasHealth = !!health
  const hasTelemetry = !!telemetry

  const items: ReadinessItem[] = [
    {
      id: 'link',
      label: 'Link',
      ok: link === 'ONLINE',
      state: link === 'ONLINE' ? 'Connected' : link === 'CONNECTING' ? 'Connecting' : link,
      detail: link === 'ONLINE' ? 'WebSocket/API reachable' : 'Check service and network',
      tone: link === 'ONLINE' ? 'ok' : link === 'CONNECTING' || link === 'TOKEN REQUIRED' || link === 'AUTH REQUIRED' ? 'warn' : 'bad',
    },
    {
      id: 'camera',
      label: 'Camera',
      ok: !!health?.camera.available,
      state: !hasHealth ? 'Checking' : health.camera.available ? 'Ready' : 'Offline',
      detail: !hasHealth ? 'Waiting for health' : health.camera.error || (health.camera.available ? 'Video feed available' : 'No camera feed'),
      tone: !hasHealth ? 'neutral' : health.camera.available ? 'ok' : 'warn',
    },
    {
      id: 'pan',
      label: 'Pan calibrated',
      ok: !!telemetry?.axes.pan.calibrated,
      state: !hasTelemetry ? 'Checking' : telemetry.axes.pan.calibrated ? 'Calibrated' : 'Required',
      detail: !hasTelemetry ? 'Waiting for telemetry' : telemetry.axes.pan.calibrated ? `${telemetry.axes.pan.deg.toFixed(1)}°` : 'Set current zero',
      tone: !hasTelemetry ? 'neutral' : telemetry.axes.pan.calibrated ? 'ok' : 'warn',
    },
    {
      id: 'tilt',
      label: 'Tilt calibrated',
      ok: !!telemetry?.axes.tilt.calibrated,
      state: !hasTelemetry ? 'Checking' : telemetry.axes.tilt.calibrated ? 'Calibrated' : 'Required',
      detail: !hasTelemetry ? 'Waiting for telemetry' : telemetry.axes.tilt.calibrated ? `${telemetry.axes.tilt.deg.toFixed(1)}°` : 'Set current zero',
      tone: !hasTelemetry ? 'neutral' : telemetry.axes.tilt.calibrated ? 'ok' : 'warn',
    },
    {
      id: 'safety',
      label: 'Faults / E-STOP',
      ok: hasTelemetry && !telemetry.interlocks.estop && !telemetry.fault && !telemetry.throttled,
      state: !hasTelemetry ? 'Checking' : telemetry.interlocks.estop ? 'E-STOP' : telemetry.fault ? 'Fault' : telemetry.throttled ? 'Throttle' : 'Clear',
      detail: !hasTelemetry
        ? 'Waiting for telemetry'
        : telemetry.interlocks.estop
          ? 'Latched'
          : telemetry.fault || (telemetry.throttled ? 'Power/thermal issue' : 'No active fault'),
      tone: !hasTelemetry ? 'neutral' : telemetry.interlocks.estop || telemetry.fault || telemetry.throttled ? 'bad' : 'ok',
    },
  ]

  const readyCount = items.filter((i) => i.ok).length
  const total = items.length
  const hasBad = items.some((i) => i.tone === 'bad')
  const allOk = readyCount === total
  const checking = items.some((i) => i.tone === 'neutral')

  return { items, readyCount, total, allOk, hasBad, checking }
}
