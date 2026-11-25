import { useCallback, useEffect, useRef, useState } from 'react'

type Props = {
  disabled: boolean
  onMove: (pan: number, tilt: number) => void
  onEnd: () => void
}

export function JoystickControl({ disabled, onMove, onEnd }: Props) {
  const baseRef = useRef<HTMLDivElement | null>(null)
  const active = useRef(false)
  const pointerId = useRef<number | null>(null)
  const [knob, setKnob] = useState({ x: 0, y: 0 })
  const [engaged, setEngaged] = useState(false)

  const stop = useCallback(() => {
    if (!active.current) {
      setKnob({ x: 0, y: 0 })
      setEngaged(false)
      return
    }
    active.current = false
    pointerId.current = null
    setKnob({ x: 0, y: 0 })
    setEngaged(false)
    onEnd()
  }, [onEnd])

  const updateFromEvent = useCallback((clientX: number, clientY: number) => {
    const base = baseRef.current
    if (!base) return
    const rect = base.getBoundingClientRect()
    const radius = rect.width / 2
    const max = radius - 28
    const dx = clientX - (rect.left + radius)
    const dy = clientY - (rect.top + radius)
    const dist = Math.hypot(dx, dy) || 1
    const clamped = Math.min(dist, max)
    const nx = (dx / dist) * clamped
    const ny = (dy / dist) * clamped
    setKnob({ x: nx, y: ny })
    const pan = Math.max(-1, Math.min(1, nx / max))
    const tilt = Math.max(-1, Math.min(1, -ny / max))
    const dead = 0.12
    onMove(Math.abs(pan) < dead ? 0 : pan, Math.abs(tilt) < dead ? 0 : tilt)
  }, [onMove])

  useEffect(() => {
    if (disabled) stop()
  }, [disabled, stop])

  useEffect(() => {
    const onPointerMove = (e: PointerEvent) => {
      if (!active.current || e.pointerId !== pointerId.current) return
      updateFromEvent(e.clientX, e.clientY)
    }
    const onPointerUp = (e: PointerEvent) => {
      if (e.pointerId !== pointerId.current) return
      stop()
    }
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerUp)
    window.addEventListener('blur', stop)
    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('pointercancel', onPointerUp)
      window.removeEventListener('blur', stop)
    }
  }, [stop, updateFromEvent])

  return (
    <div className="joystick-wrap">
      <div
        ref={baseRef}
        className={`joystick-base ${disabled ? 'is-disabled' : ''} ${engaged ? 'is-engaged' : ''}`}
        role="application"
        aria-label="Pan tilt joystick"
        aria-disabled={disabled}
        onPointerDown={(e) => {
          if (disabled) return
          e.preventDefault()
          active.current = true
          pointerId.current = e.pointerId
          setEngaged(true)
          ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
          updateFromEvent(e.clientX, e.clientY)
        }}
      >
        <div className="joystick-ring" aria-hidden="true" />
        <div className="joystick-cross" aria-hidden="true"><span /><span /></div>
        <div className="joystick-knob" style={{ transform: `translate(calc(-50% + ${knob.x}px), calc(-50% + ${knob.y}px))` }} aria-hidden="true" />
        <div className="joystick-dir joystick-n">TILT +</div>
        <div className="joystick-dir joystick-s">TILT -</div>
        <div className="joystick-dir joystick-w">PAN -</div>
        <div className="joystick-dir joystick-e">PAN +</div>
      </div>
    </div>
  )
}
