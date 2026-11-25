import { useCallback, useMemo } from 'react'
import {
  calibrateAxes,
  estop,
  fetchConfig,
  fetchLog,
  homeAxes,
  saveConfig,
  sendJog,
  setMode,
} from '../services/api'
import type { Mode, Tuning } from '../types/prahari'

export function usePrahariApi(token: string, onAuthError: () => void) {
  const wrap = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T> => {
      try {
        return await fn()
      } catch (e) {
        const err = e as Error & { status?: number }
        if (err.status === 401) onAuthError()
        throw err
      }
    },
    [onAuthError],
  )

  return useMemo(() => ({
    loadConfig: () => wrap(() => fetchConfig(token)),
    saveConfig: (payload: Tuning) => wrap(() => saveConfig(token, payload)),
    loadLog: (limit = 200) => wrap(() => fetchLog(token, limit)),
    setMode: (mode: Mode) => wrap(() => setMode(token, mode)),
    jog: (pan: number, tilt: number) => wrap(() => sendJog(token, pan, tilt)),
    home: () => wrap(() => homeAxes(token)),
    calibrate: () => wrap(() => calibrateAxes(token)),
    estop: async () => {
      const res = await estop()
      if (!res.ok) throw new Error('E-STOP request failed')
      return res
    },
  }), [token, wrap])
}
