import type { Health, LogResponse, Mode, Telemetry, Tuning } from '../types/prahari'

export const TOKEN_KEY = 'prahari-token'

export function getStoredToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) || ''
}

export function storeToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

export function authHeaders(token: string): Record<string, string> {
  return token ? { 'X-Token': token } : {}
}

export function withTokenQuery(path: string, token: string): string {
  const url = new URL(path, window.location.origin)
  if (token) url.searchParams.set('token', token)
  return url.toString()
}

async function parseError(response: Response): Promise<string> {
  let message = response.statusText || `Request failed (${response.status})`
  try {
    const body = (await response.json()) as { detail?: string }
    if (body?.detail) message = body.detail
  } catch {
    // Ignore JSON parse failures and keep status text.
  }
  return message
}

export async function apiRequest<T>(
  path: string,
  token: string,
  method = 'GET',
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(token),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const message = await parseError(response)
    const error = new Error(message) as Error & { status?: number }
    error.status = response.status
    throw error
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch('/api/health')
  if (!response.ok) throw new Error('FastAPI unavailable')
  return (await response.json()) as Health
}

export async function fetchTelemetry(token: string): Promise<Telemetry> {
  return apiRequest<Telemetry>('/api/telemetry', token)
}

export async function fetchConfig(token: string): Promise<Tuning> {
  return apiRequest<Tuning>('/api/config', token)
}

export async function saveConfig(token: string, payload: Tuning): Promise<Tuning> {
  return apiRequest<Tuning>('/api/config', token, 'PUT', {
    backend: payload.backend,
    hue_min: payload.color.hue_min,
    hue_max: payload.color.hue_max,
    saturation_min: payload.color.saturation_min,
    value_min: payload.color.value_min,
    kp: payload.control.kp,
    ki: payload.control.ki,
    kd: payload.control.kd,
  })
}

export async function fetchLog(token: string, limit = 200): Promise<LogResponse> {
  return apiRequest<LogResponse>(`/api/log?limit=${limit}`, token)
}

export async function setMode(token: string, mode: Mode): Promise<{ mode: string }> {
  return apiRequest<{ mode: string }>('/api/mode', token, 'POST', { mode })
}

export async function sendJog(token: string, pan_dps: number, tilt_dps: number): Promise<unknown> {
  return apiRequest('/api/jog', token, 'POST', { pan_dps, tilt_dps })
}

export async function homeAxes(token: string): Promise<unknown> {
  return apiRequest('/api/home', token, 'POST')
}

export async function calibrateAxes(token: string): Promise<unknown> {
  return apiRequest('/api/calibrate', token, 'POST')
}

export async function estop(): Promise<Response> {
  return fetch('/api/estop', { method: 'POST' })
}

export function telemetrySocketUrl(token: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = new URL(`${scheme}://${window.location.host}/ws/telemetry`)
  if (token) url.searchParams.set('token', token)
  return url.toString()
}
