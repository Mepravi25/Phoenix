import axios from 'axios'

/** Local storage key shared by the auth screens and Axios interceptor. */
export const ACCESS_TOKEN_KEY = 'traffic_access_token'

/** API URL is configurable at build time without hard-coding deployment hosts. */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

/** Attach the current JWT to every protected API request automatically. */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
}

export interface TrafficNode {
  id: number
  label: string
  flush_time: number
  color: string
  /** Raw queue emitted by the intersection simulator, when available. */
  queue_length?: number
  /** The direct simulator reading before the backend's STGNN projection. */
  observed_flush_time?: number
  light_phase?: 'NS_GREEN' | 'EW_GREEN' | 'YELLOW' | string
  active_direction?: 'NS' | 'EW' | null | string
  phase_remaining_ticks?: number
  /** True while this intersection is temporarily held for an EV reservation. */
  preemption_active?: boolean
  reserved_axis?: 'NS' | 'EW' | null | string
  reservation_ev_id?: string | null
  reservation_remaining_ticks?: number
  reservation_end_time?: number | null
  /** Signal state that was paused while an EV green wave is active. */
  preempted_from_phase?: 'NS_GREEN' | 'EW_GREEN' | 'YELLOW' | null | string
  preempted_from_direction?: 'NS' | 'EW' | null | string
  /** True when the watchdog or an administrator has marked this node unavailable. */
  offline?: boolean
}

export interface TrafficEdge {
  source: number
  target: number
  weight: number
  direction?: 'NS' | 'EW' | string
  signal_delay?: number
}

export interface TrafficSnapshot {
  nodes: TrafficNode[]
  edges: TrafficEdge[]
  /** How the backend obtained this snapshot (normally the MQTT simulator). */
  source?: string
  mqtt_connected?: boolean
  mqtt_error?: string | null
  traffic_available?: boolean
  traffic_stale?: boolean
  traffic_age_seconds?: number | null
  updated_at?: string
  generated_at?: string
  simulation_tick?: number
  traffic_version?: number
  active_preemptions?: number
  offline_nodes?: number[]
  reservation_control_ready?: boolean
  ingest_error?: string | null
}

export interface TrafficStatus {
  source: string
  mqtt_connected: boolean
  mqtt_error?: string | null
  traffic_available: boolean
  traffic_stale: boolean
  traffic_age_seconds?: number | null
  updated_at?: string | null
  generated_at?: string | null
  simulation_tick?: number | null
  traffic_version: number
  active_preemptions?: number
  offline_nodes?: number[]
  offline_node_count?: number
  reservation_control_ready?: boolean
  ingest_error?: string | null
}

/**
 * Physical/environmental reading for one simulated intersection. Coordinates
 * come from PostGIS while the metrics are calculated from the live queue.
 */
export interface EnvironmentHeatmapPoint {
  node_id: number
  lat: number
  lon: number
  queue_length: number
  uhi_index: number
  emission_index: number
}

export interface RouteSegment {
  from: number
  to: number
  direction?: 'NS' | 'EW' | string
  /** Time spent travelling the road after the signal permits the movement. */
  road_travel_seconds?: number
  /** Time the ambulance remains at the source intersection for this signal. */
  signal_wait_seconds?: number
  /** Backward-compatible total: road travel plus signal wait. */
  travel_cost?: number
  congestion_cost?: number
  signal_delay?: number
  source_light_phase?: string
  source_active_direction?: string | null
  phase_remaining_ticks?: number
  /** FCFS booking details, present for route legs within the 120-second horizon. */
  reservation_start_time?: number | null
  reservation_duration_seconds?: number | null
  reservation_id?: string | null
  reservation_status?: 'granted' | string | null
}

export interface ReservationWindow {
  node: number
  ev_id: string
  axis: 'NS' | 'EW' | string
  start_time: number
  duration: number
  granted: boolean
  request_id: string
  reservation_id: string
}

export interface RouteResponse {
  path: number[]
  eta_seconds: number
  eta_minutes?: number
  recommended_route?: string[]
  traffic_level?: string
  reason?: string
  simulation_status?: string
  simulation_connected?: boolean
  success?: boolean
  error?: string
  /** The live traffic revision used to calculate this route. */
  traffic_version?: number
  traffic_age_seconds?: number
  traffic_source?: string
  generated_at?: string
  segments?: RouteSegment[]
  ev_id?: string
  reservation_status?: string | null
  reservations?: ReservationWindow[]
  reservation_attempts?: number
  reservation_horizon_limited?: boolean
  excluded_nodes?: number[]
}

export interface RouteCancellationResponse {
  ev_id: string
  cancelled_reservations: number
  status: 'cancelled' | 'cancellation_queued' | string
}

export interface CurrentUser {
  id: number
  username: string
  role: string
}

export default api
