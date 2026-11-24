import { Camera, Crosshair, ShieldAlert, Video } from 'lucide-react'
import type { Health, Telemetry } from '../types/prahari'
import { fmt } from '../utils'

type Props = {
  health: Health | null
  telemetry: Telemetry | null
  videoUrl: string
  banner: string
  bannerBad: boolean
  locked: boolean
  sim: boolean
  axesCalibrated: boolean
  link: string
}

const AZ_MIN = -90
const AZ_MAX = 90
const EL_MIN = -60
const EL_MAX = 60

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function pct(value: number, min: number, max: number) {
  return ((value - min) / (max - min)) * 100
}

export function CameraViewport({
  health,
  telemetry,
  videoUrl,
  banner,
  bannerBad,
  locked,
  sim,
  axesCalibrated,
  link,
}: Props) {
  const cameraAvailable = !!health?.camera.available
  const disconnected = !cameraAvailable || link === 'SERVICE OFFLINE' || link === 'DISCONNECTED' || link === 'LINK ERROR'
  const reconnecting = link === 'CONNECTING'
  const live = cameraAvailable && !disconnected && !reconnecting
  const target = telemetry?.target ?? null
  const mode = (telemetry?.mode ?? 'idle').toUpperCase()
  const az = telemetry?.axes.pan.deg ?? 0
  const el = telemetry?.axes.tilt.deg ?? 0
  const azPct = clamp(pct(az, AZ_MIN, AZ_MAX), 0, 100)
  const elPct = clamp(pct(el, EL_MIN, EL_MAX), 0, 100)
  const targetState = target ? (locked ? 'TARGET LOCKED' : 'TARGET ACQUIRED') : 'NO TARGET'

  return (
    <section className="panel camera-panel eo-camera-panel" aria-labelledby="camera-title">
      <div className="eo-frame">
        <div className="eo-corner eo-corner-tl" aria-hidden="true" />
        <div className="eo-corner eo-corner-tr" aria-hidden="true" />
        <div className="eo-corner eo-corner-bl" aria-hidden="true" />
        <div className="eo-corner eo-corner-br" aria-hidden="true" />

        <div className="eo-topbar">
          <div className="eo-title" id="camera-title">
            <Video size={14} aria-hidden="true" />
            <span>EO LIVE VIEW</span>
            <span className={`eo-live ${live ? 'is-live' : disconnected ? 'is-offline' : 'is-warn'}`}>
              <span className="eo-live-dot" aria-hidden="true" />
              {live ? 'LIVE' : reconnecting ? 'RECONNECTING' : 'OFFLINE'}
            </span>
          </div>
          <div className="eo-metrics" aria-label="Camera telemetry">
            <span>FPS: <strong>{fmt(telemetry?.fps, 0)}</strong></span>
            <span className="eo-metrics-sep">|</span>
            <span>{fmt(telemetry?.latency_ms ?? health?.camera.age_ms, 0)} ms</span>
          </div>
        </div>

        <div className="eo-viewport">
          <img
            src={videoUrl}
            alt="Live camera feed"
            className="eo-video"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.opacity = '0' }}
            onLoad={(e) => { (e.currentTarget as HTMLImageElement).style.opacity = '1' }}
          />
          <div className="eo-video-fallback" aria-hidden="true">
            <Camera size={30} />
            <strong>OPTICAL FEED UNAVAILABLE</strong>
            <span>{health?.camera.error || (reconnecting ? 'Reconnecting to camera service' : 'Connect to local service and camera')}</span>
          </div>

          <div className="eo-overlay" aria-hidden="true">
            <div className="eo-elevation">
              <div className="eo-scale eo-scale-v">
                <span className="eo-scale-label" style={{ top: '0%' }}>+60°</span>
                <span className="eo-scale-label" style={{ top: '25%' }}>+30°</span>
                <span className="eo-scale-label" style={{ top: '50%' }}>0°</span>
                <span className="eo-scale-label" style={{ top: '75%' }}>-30°</span>
                <span className="eo-scale-label" style={{ top: '100%' }}>-60°</span>
                {Array.from({ length: 25 }).map((_, i) => {
                  const top = (i / 24) * 100
                  const major = i % 6 === 0
                  const mid = i % 3 === 0
                  return <span key={i} className={`eo-tick-v ${major ? 'major' : mid ? 'mid' : ''}`} style={{ top: `${top}%` }} />
                })}
                <span className="eo-pointer-v" style={{ top: `${100 - elPct}%` }} />
              </div>
            </div>

            <div className="eo-azimuth">
              <div className="eo-scale eo-scale-h">
                <span className="eo-scale-label-h" style={{ left: '0%' }}>-90°</span>
                <span className="eo-scale-label-h" style={{ left: '25%' }}>-45°</span>
                <span className="eo-scale-label-h" style={{ left: '50%' }}>0°</span>
                <span className="eo-scale-label-h" style={{ left: '75%' }}>+45°</span>
                <span className="eo-scale-label-h" style={{ left: '100%' }}>+90°</span>
                {Array.from({ length: 37 }).map((_, i) => {
                  const left = (i / 36) * 100
                  const major = i % 9 === 0
                  const mid = i % 3 === 0
                  return <span key={i} className={`eo-tick-h ${major ? 'major' : mid ? 'mid' : ''}`} style={{ left: `${left}%` }} />
                })}
                <span className="eo-pointer-h" style={{ left: `${azPct}%` }} />
              </div>
              <div className="eo-az-label">AZIMUTH</div>
            </div>

            <svg className="eo-hud" viewBox="0 0 1000 562" preserveAspectRatio="none">
              <line x1="120" y1="281" x2="880" y2="281" className="eo-ref-line" />
              <line x1="500" y1="70" x2="500" y2="492" className="eo-ref-line" />
              <g className="eo-center-cross">
                <line x1="488" y1="281" x2="512" y2="281" />
                <line x1="500" y1="269" x2="500" y2="293" />
              </g>
              <g className="eo-brackets">
                <path d="M445 236h18M445 236v18M555 236h-18M555 236v18M445 326h18M445 326v-18M555 326h-18M555 326v-18" />
              </g>
              {target && (() => {
                const tx = (target.x / 640) * 1000
                const ty = (target.y / 480) * 562
                const tw = (target.w / 640) * 1000
                const th = (target.h / 480) * 562
                const x = tx - tw / 2
                const y = ty - th / 2
                const c = Math.max(10, Math.min(22, tw / 5, th / 5))
                return (
                  <g className={locked ? 'eo-target locked' : 'eo-target'}>
                    <rect x={x} y={y} width={tw} height={th} />
                    <path d={`M${x} ${y + c}V${y}h${c} M${x + tw - c} ${y}h${c}v${c} M${x + tw} ${y + th - c}v${c}h-${c} M${x + c} ${y + th}H${x}v-${c}`} className="eo-target-corners" />
                  </g>
                )
              })()}
            </svg>
          </div>

          <div className={`eo-status eo-status-left ${locked ? 'is-locked' : ''}`}>
            <div className="eo-status-title"><Crosshair size={13} aria-hidden="true" /> {targetState}</div>
            <div className="eo-status-sub">{target ? `(x: ${Math.round(target.x)}, y: ${Math.round(target.y)})` : 'Scanning optical field'}</div>
          </div>

          <div className="eo-status eo-status-right">
            <div className="eo-status-line"><span>ZOOM:</span> <strong>1.0x</strong></div>
            <div className="eo-status-line"><span>MODE:</span> <strong>{mode}</strong></div>
          </div>

          {banner && (
            <div className={`eo-banner ${bannerBad ? 'bad' : 'warn'}`} role="status">
              <ShieldAlert size={14} aria-hidden="true" />
              <span>{banner}</span>
            </div>
          )}
          {!banner && !axesCalibrated && (
            <div className="eo-banner warn" role="status">
              <ShieldAlert size={14} aria-hidden="true" />
              <span>Calibration required before motion modes.</span>
            </div>
          )}
          {sim && <div className="eo-sim-badge">SIMULATION FEED</div>}
        </div>
      </div>
    </section>
  )
}
