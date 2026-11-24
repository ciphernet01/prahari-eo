import { useCallback } from 'react'
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

  return {
    loadConfig: useCallback(() => wrap(() => fetchConfig(token)), [token, wrap]),
    saveConfig: useCallback((payload: Tuning) => wrap(() => saveConfig(token, payload)), [token, wrap]),
    loadLog: useCallback((limit = 200) => wrap(() => fetchLog(token, limit)), [token, wrap]),
    setMode: useCallback((mode: Mode) => wrap(() => setMode(token, mode)), [token, wrap]),
    jog: useCallback((pan: number, tilt: number) => wrap(() => sendJog(token, pan, tilt)), [token, wrap]),
    home: useCallback(() => wrap(() => homeAxes(token)), [token, wrap]),
    calibrate: useCallback(() => wrap(() => calibrateAxes(token)), [token, wrap]),
    estop: useCallback(async () => {
      const res = await estop()
      if (!res.ok) throw new Error('E-STOP request failed')
      return res
    }, []),
  }
}
