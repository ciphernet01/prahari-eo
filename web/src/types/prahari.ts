export type CameraStatus = {
  available: boolean
  age_ms: number | null
  error?: string | null
  simulation?: boolean
}

export type Health = {
  status: string
  simulation?: boolean
  camera: CameraStatus
  state: string
  home_switches_enabled: boolean
  buzzer_enabled: boolean
  cpu_temp_c?: number | null
  throttled?: boolean
  throttle_flags_hex?: string | null
  throttle_active_flags_hex?: string | null
  throttle_history_flags_hex?: string | null
  pi_5v_v?: number | null
  auth_required: boolean
}

export type AxisTelemetry = {
  deg: number
  calibrated: boolean
  velocity_dps: number
  fault?: string | null
}

export type TargetTelemetry = {
  x: number
  y: number
  w: number
  h: number
  conf: number
}

export type Telemetry = {
  state: string
  mode: string
  interlocks: {
    arm_enabled: boolean
    deadman: boolean
    estop: boolean
  }
  axes: {
    pan: AxisTelemetry
    tilt: AxisTelemetry
  }
  target: TargetTelemetry | null
  err_x: number
  err_y: number
  lock_frames: number
  fault?: string | null
  latency_ms: number
  fps: number
  cpu_temp_c: number | null
  throttled: boolean
  simulation?: boolean
  camera?: CameraStatus
  angular_error_deg?: { pan: number; tilt: number }
  throttle_flags_hex?: string | null
  throttle_active_flags_hex?: string | null
  throttle_history_flags_hex?: string | null
  pi_5v_v?: number | null
}

export type Tuning = {
  backend: string
  color: {
    hue_min: number
    hue_max: number
    saturation_min: number
    value_min: number
  }
  control: {
    kp: number
    ki: number
    kd: number
  }
}

export type LogRow = {
  time: number
  event: string
  [key: string]: unknown
}

export type LogResponse = {
  events: LogRow[]
}

export type Mode = 'idle' | 'manual' | 'auto'
