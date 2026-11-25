import { ShieldAlert, Video } from 'lucide-react'
import type { Health, Telemetry } from '../types/prahari'

type Props = {
  health: Health | null
  telemetry: Telemetry | null
  videoUrl: string
  banner: string
  bannerBad: boolean
  axesCalibrated: boolean
  link: string
}

export function CameraViewport({
  health,
  telemetry,
  videoUrl,
  banner,
  bannerBad,
  axesCalibrated,
  link,
}: Props) {
  const cameraAvailable = !!health?.camera.available
  const disconnected = !cameraAvailable || link === 'SERVICE OFFLINE' || link === 'DISCONNECTED' || link === 'LINK ERROR'
  const reconnecting = link === 'CONNECTING'
  const live = cameraAvailable && !disconnected && !reconnecting
  const target = telemetry?.target ?? null
  const pan = telemetry?.axes.pan.calibrated ? telemetry.axes.pan.deg : null
  const tilt = telemetry?.axes.tilt.calibrated ? telemetry.axes.tilt.deg : null
  const targetStatus = !health?.camera.available
    ? health ? 'CAMERA OFFLINE' : 'WAITING FOR DATA'
    : target ? 'TARGET ACQUIRED' : telemetry ? 'NO TARGET' : 'WAITING FOR DATA'

  return (
    <section className="panel camera-panel eo-camera-panel" aria-labelledby="camera-title">
      <div className="eo-frame">
        <div className="eo-topbar">
          <div className="eo-title" id="camera-title">
            <Video size={14} aria-hidden="true" />
            <span>EO LIVE VIEW</span>
            <span className={`eo-live ${live ? 'is-live' : disconnected ? 'is-offline' : 'is-warn'}`}>
              <span className="eo-live-dot" aria-hidden="true" />
              {live ? 'LIVE' : reconnecting ? 'RECONNECTING' : 'OFFLINE'}
            </span>
          </div>
        </div>

        <div className="eo-viewport">
          <img
            src={videoUrl}
            alt="Live camera feed"
            className="eo-video"
            onError={(e) => { e.currentTarget.style.opacity = '0' }}
            onLoad={(e) => { e.currentTarget.style.opacity = '1' }}
          />

          <div className="eo-hud-grid" aria-hidden="true" />
          <div className="eo-reticle" aria-hidden="true">
            <span />
          </div>
          <div className="eo-hud-readout eo-hud-readout-top" aria-label="Camera position">
            <span>PAN <strong>{pan == null ? '--' : `${pan.toFixed(1)}°`}</strong></span>
            <span>TILT <strong>{tilt == null ? '--' : `${tilt.toFixed(1)}°`}</strong></span>
          </div>
          <div className="eo-hud-readout eo-hud-readout-bottom" aria-label="Target tracking">
            <span className="eo-track-indicator" />
            <span>{targetStatus}</span>
            <span className="eo-hud-divider">/</span>
            <span>CONF <strong>{target ? `${Math.round(target.conf * 100)}%` : '--'}</strong></span>
          </div>

          {banner && (
            <div className={`eo-banner ${bannerBad ? 'bad' : 'warn'}`} role="status">
              <ShieldAlert size={14} aria-hidden="true" />
              <span>{banner}</span>
            </div>
          )}
          {!banner && telemetry && !axesCalibrated && (
            <div className="eo-banner warn" role="status">
              <ShieldAlert size={14} aria-hidden="true" />
              <span>Calibration required before motion modes.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
