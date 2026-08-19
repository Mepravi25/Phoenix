import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import L from 'leaflet'
import ForceGraph2D from 'react-force-graph-2d'
import { MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Toolbar,
  Typography,
} from '@mui/material'
import axios from 'axios'

import api, {
  ACCESS_TOKEN_KEY,
  API_BASE_URL,
  type EnvironmentHeatmapPoint,
  type CurrentUser,
  type RouteCancellationResponse,
  type RouteResponse,
  type RouteSegment,
  type TrafficEdge,
  type TrafficNode,
  type TrafficSnapshot,
  type TrafficStatus,
} from './api'

type GraphNode = TrafficNode & { name: string, x: number, y: number, fx: number, fy: number }
type GraphLink = TrafficEdge
type TripStatus = 'active' | 'arrived' | 'retrying'
type MotionStage = 'waiting_for_signal' | 'travelling'
type EmergencyVehicleType = 'ambulance' | 'fire_truck' | 'police_vehicle' | 'rescue_vehicle'

type ActiveTrip = {
  currentLocation: number
  destination: number
  route: RouteResponse
  status: TripStatus
  motionStage: MotionStage
  vehicleType: EmergencyVehicleType
}

type RouteHistoryEntry = {
  currentLocation: number
  nextLocation: number
  route: number[]
  totalSeconds: number
  roadTravelSeconds: number
  signalWaitSeconds: number
  trafficVersion?: number
  lightPhase?: string
}

type TrafficHistoryPoint = {
  tick: number
  totalQueue: number
  trafficVersion: number
}

const INTERSECTIONS = Array.from({ length: 25 }, (_, node) => node)
const NODE_NAMES = [
  'North Gate', 'North Market', 'University', 'North Park', 'East Gate',
  'West Market', 'Civic Centre', 'Hospital District', 'Museum Row', 'East Market',
  'River West', 'Central Square', 'Medical HQ', 'City Hall', 'River East',
  'South Market', 'Stadium', 'Tech Park', 'Garden Junction', 'South East',
  'West Depot', 'Old Town', 'Transit Hub', 'Lakeside Medical Centre', 'South Gate',
] as const
const HOSPITAL_NODE_IDS = [7, 12, 23] as const
const EMERGENCY_VEHICLES: { value: EmergencyVehicleType; label: string }[] = [
  { value: 'ambulance', label: 'Ambulance' },
  { value: 'fire_truck', label: 'Fire truck' },
  { value: 'police_vehicle', label: 'Police vehicle' },
  { value: 'rescue_vehicle', label: 'Rescue vehicle' },
]
const MAP_VIEWBOX_WIDTH = 165
const MAP_VIEWBOX_HEIGHT = 100
const CITY_GRID_ROADS = INTERSECTIONS.flatMap((node) => {
  const row = Math.floor(node / 5)
  const column = node % 5
  return [
    ...(column < 4 ? [[node, node + 1] as const] : []),
    ...(row < 4 ? [[node, node + 5] as const] : []),
  ]
})
// One simulated second maps to one real second by default, keeping EV movement
// aligned with the one-second traffic-light ticks from intersection_agent.py.
// A deployment may lower this only when deliberately running a faster demo.
const EV_SECONDS_PER_ETA_SECOND = Math.max(
  0.01,
  Number(import.meta.env.VITE_EV_SECONDS_PER_ETA_SECOND ?? 1),
)
const RETRY_REQUEST_DELAY_MS = 1_000
const STATUS_POLL_MS = 3_000
type GeoCoordinate = [number, number]

// A geographic reference frame for the existing synthetic 5×5 operations
// grid. It is intentionally only a map overlay: node IDs, traffic values and
// route calculation continue to use the simulator's grid topology.
const COIMBATORE_GRID_COORDINATES: GeoCoordinate[] = [
  [11.0495, 76.9415], [11.0462, 76.9558], [11.0480, 76.9706], [11.0451, 76.9856], [11.0490, 76.9995],
  [11.0365, 76.9398], [11.0320, 76.9540], [11.0350, 76.9682], [11.0315, 76.9827], [11.0353, 76.9984],
  [11.0228, 76.9432], [11.0185, 76.9582], [11.0224, 76.9727], [11.0190, 76.9875], [11.0232, 77.0014],
  [11.0085, 76.9395], [11.0045, 76.9554], [11.0088, 76.9702], [11.0049, 76.9844], [11.0082, 76.9988],
  [10.9936, 76.9430], [10.9902, 76.9580], [10.9934, 76.9726], [10.9906, 76.9868], [10.9940, 77.0002],
]
const COIMBATORE_BOUNDS: [GeoCoordinate, GeoCoordinate] = [
  [10.9870, 76.9370],
  [11.0530, 77.0030],
]

function trafficWebSocketUrl(): string {
  const configured = import.meta.env.VITE_TRAFFIC_WS_URL
  if (configured) return configured

  try {
    const apiUrl = new URL(API_BASE_URL)
    const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${apiUrl.host}/ws/traffic`
  } catch {
    return 'ws://localhost:8000/ws/traffic'
  }
}

const TRAFFIC_WS_URL = trafficWebSocketUrl()

function routeErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail ?? 'Unable to calculate a priority route.'
  }
  return 'Unable to calculate a priority route. Please try again.'
}

function environmentErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail ?? 'Unable to load the environmental overlay.'
  }
  return 'Unable to load the environmental overlay. Please try again.'
}

function statusFromSnapshot(snapshot: TrafficSnapshot): TrafficStatus {
  return {
    source: snapshot.source ?? 'awaiting_mqtt',
    mqtt_connected: Boolean(snapshot.mqtt_connected),
    mqtt_error: snapshot.mqtt_error,
    traffic_available: Boolean(snapshot.traffic_available),
    traffic_stale: Boolean(snapshot.traffic_stale),
    traffic_age_seconds: snapshot.traffic_age_seconds,
    updated_at: snapshot.updated_at,
    generated_at: snapshot.generated_at,
    simulation_tick: snapshot.simulation_tick,
    traffic_version: snapshot.traffic_version ?? 0,
    active_preemptions: snapshot.active_preemptions ?? 0,
    offline_nodes: snapshot.offline_nodes ?? snapshot.nodes.filter((node) => node.offline).map((node) => node.id),
    offline_node_count: snapshot.offline_nodes?.length ?? snapshot.nodes.filter((node) => node.offline).length,
    reservation_control_ready: snapshot.reservation_control_ready ?? false,
    ingest_error: snapshot.ingest_error,
  }
}

function formatAge(seconds?: number | null): string {
  if (seconds === undefined || seconds === null) return 'waiting for data'
  if (seconds < 1) return 'just now'
  return `${seconds.toFixed(1)}s ago`
}

function mapCoordinate(node: number): { x: number, y: number } {
  const row = Math.floor(node / 5)
  const column = node % 5
  // Keep a small border around the virtual 5×5 street grid. The view box has
  // the same aspect ratio as its panel, avoiding the former empty side area.
  return {
    x: MAP_VIEWBOX_WIDTH * (0.10 + (column * 0.20)),
    y: MAP_VIEWBOX_HEIGHT * (0.10 + (row * 0.20)),
  }
}

function nodeName(node: number): string {
  return NODE_NAMES[node] ?? `Node ${node}`
}

function nodeDisplayName(node: number): string {
  return `${nodeName(node)} (#${node})`
}

function emergencyVehicleLabel(vehicleType: EmergencyVehicleType): string {
  return EMERGENCY_VEHICLES.find((vehicle) => vehicle.value === vehicleType)?.label ?? 'Emergency vehicle'
}

function emergencyVehicleEmoji(vehicleType: EmergencyVehicleType): string {
  return {
    ambulance: '🚑',
    fire_truck: '🚒',
    police_vehicle: '🚓',
    rescue_vehicle: '🚐',
  }[vehicleType]
}

function gridDistance(from: number, to: number): number {
  return Math.abs(Math.floor(from / 5) - Math.floor(to / 5)) + Math.abs((from % 5) - (to % 5))
}

function nearestHospitalNodes(from: number): number[] {
  return [...HOSPITAL_NODE_IDS]
    .filter((node) => node !== from)
    .sort((first, second) => gridDistance(from, first) - gridDistance(from, second))
}

function adminGraphCoordinate(node: number): { x: number, y: number } {
  const row = Math.floor(node / 5)
  const column = node % 5
  return { x: (column - 2) * 118, y: (row - 2) * 104 }
}

function preemptionLabel(node: TrafficNode): string {
  const previousDirection = node.preempted_from_direction
  const previous = node.preempted_from_phase === 'YELLOW'
    ? `Y · ${previousDirection ?? '—'}`
    : previousDirection ?? 'Normal signal'
  const reserved = node.reserved_axis ?? node.active_direction ?? '—'
  return `${previous} → EV ${reserved}`
}

function signalWaitSeconds(route: RouteResponse): number {
  const segment = route.segments?.[0]
  return Math.max(0, segment?.signal_wait_seconds ?? segment?.signal_delay ?? 0)
}

function roadTravelSeconds(route: RouteResponse): number {
  const segment = route.segments?.[0]
  const routeLegs = Math.max(1, route.path.length - 1)
  const totalSeconds = segment?.travel_cost ?? route.eta_seconds / routeLegs
  const roadSeconds = segment?.road_travel_seconds ?? segment?.congestion_cost
  return Math.max(0, roadSeconds ?? totalSeconds - signalWaitSeconds(route))
}

function realTimeDelayMilliseconds(simulatedSeconds: number): number {
  return Math.max(0, simulatedSeconds * EV_SECONDS_PER_ETA_SECOND * 1_000)
}

function motionStageForRoute(route: RouteResponse): MotionStage {
  return signalWaitSeconds(route) > 0 ? 'waiting_for_signal' : 'travelling'
}

function latestSegment(route: RouteResponse): RouteSegment | undefined {
  return route.segments?.[0]
}

function reservationWindowLabel(segment?: RouteSegment): string | null {
  if (
    !segment ||
    segment.reservation_status !== 'granted' ||
    segment.reservation_start_time === undefined ||
    segment.reservation_start_time === null
  ) return null

  const localStart = new Date(segment.reservation_start_time * 1_000)
  const time = localStart.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const duration = segment.reservation_duration_seconds ?? 0
  return `FCFS signal slot ${time} for ${duration}s`
}

function telemetrySeverity(status: TrafficStatus | null): 'success' | 'warning' | 'error' | 'info' {
  if (!status) return 'info'
  if (status.traffic_stale) return 'warning'
  if (status.mqtt_connected) return 'success'
  return 'warning'
}

/** Live, authenticated React interface for administrators and EV drivers. */
export default function Dashboard() {
  const navigate = useNavigate()
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [traffic, setTraffic] = useState<TrafficSnapshot | null>(null)
  const [trafficStatus, setTrafficStatus] = useState<TrafficStatus | null>(null)
  const [socketConnected, setSocketConnected] = useState(false)
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(24)
  const [vehicleType, setVehicleType] = useState<EmergencyVehicleType>('ambulance')
  const [destinationSelected, setDestinationSelected] = useState(false)
  const [routeError, setRouteError] = useState<string | null>(null)
  const [isRouting, setIsRouting] = useState(false)
  const [trip, setTrip] = useState<ActiveTrip | null>(null)
  const [isReplanning, setIsReplanning] = useState(false)
  const [routeHistory, setRouteHistory] = useState<RouteHistoryEntry[]>([])
  const [trafficHistory, setTrafficHistory] = useState<TrafficHistoryPoint[]>([])

  const isAdmin = currentUser?.role === 'admin'
  const currentLocation = trip?.currentLocation ?? start
  const isTripInProgress = Boolean(trip && trip.status !== 'arrived')

  const graphData = useMemo<{ nodes: GraphNode[]; links: GraphLink[] }>(
    () => ({
      nodes: (traffic?.nodes ?? []).map((node) => {
        const position = adminGraphCoordinate(node.id)
        return { ...node, name: node.label, ...position, fx: position.x, fy: position.y }
      }),
      links: (traffic?.edges ?? []).map((edge) => ({ ...edge })),
    }),
    [traffic],
  )

  const congestionTotals = useMemo(() => {
    if (!traffic?.traffic_available) return { clear: 0, moderate: 0, heavy: 0, offline: 0 }
    const nodes = traffic?.nodes ?? []
    return nodes.reduce(
      (totals, node) => {
        if (node.offline) totals.offline += 1
        else if (node.flush_time >= 18) totals.heavy += 1
        else if (node.flush_time >= 10) totals.moderate += 1
        else totals.clear += 1
        return totals
      },
      { clear: 0, moderate: 0, heavy: 0, offline: 0 },
    )
  }, [traffic])

  useEffect(() => {
    let active = true
    api.get<CurrentUser>('/api/me')
      .then((response) => {
        if (active) {
          setCurrentUser(response.data)
          if (window.location.pathname === '/admin' && response.data.role !== 'admin') {
            navigate('/dashboard', { replace: true })
          }
        }
      })
      .catch(() => {
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        navigate('/login', { replace: true })
      })
    return () => { active = false }
  }, [navigate])

  useEffect(() => {
    if (!currentUser || isAdmin) return undefined

    let active = true
    const fetchStatus = () => {
      api.get<TrafficStatus>('/api/traffic/status')
        .then((response) => {
          if (active) setTrafficStatus(response.data)
        })
        .catch(() => {
          // A route request will show the actionable server error; avoid
          // replacing it with a noisy background polling failure.
        })
    }
    fetchStatus()
    const timer = window.setInterval(fetchStatus, STATUS_POLL_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [currentUser, isAdmin])

  useEffect(() => {
    if (!isAdmin) return undefined

    let socket: WebSocket | undefined
    let reconnectTimer: number | undefined
    let disposed = false

    const recordTrafficHistory = (snapshot: TrafficSnapshot) => {
      if (!snapshot.traffic_available || snapshot.simulation_tick === undefined) return
      const totalQueue = snapshot.nodes.reduce(
        (total, node) => total + (node.queue_length ?? 0),
        0,
      )
      setTrafficHistory((history) => {
        const latest = history.at(-1)
        if (latest?.trafficVersion === snapshot.traffic_version) return history
        return [
          ...history,
          {
            tick: snapshot.simulation_tick ?? 0,
            totalQueue,
            trafficVersion: snapshot.traffic_version ?? 0,
          },
        ].slice(-30)
      })
    }

    const loadFallbackSnapshot = () => {
      api.get<TrafficSnapshot>('/api/traffic/snapshot')
        .then((response) => {
          if (!disposed) {
            setTraffic(response.data)
            setTrafficStatus(statusFromSnapshot(response.data))
            recordTrafficHistory(response.data)
          }
        })
        .catch(() => undefined)
    }

    const connect = () => {
      const token = localStorage.getItem(ACCESS_TOKEN_KEY) ?? ''
      const connection = new WebSocket(`${TRAFFIC_WS_URL}?token=${encodeURIComponent(token)}`)
      socket = connection
      connection.onopen = () => {
        if (disposed) {
          connection.close()
          return
        }
        setSocketConnected(true)
      }
      connection.onmessage = (event) => {
        try {
          const snapshot = JSON.parse(event.data) as TrafficSnapshot
          if (!disposed) {
            setTraffic(snapshot)
            setTrafficStatus(statusFromSnapshot(snapshot))
            recordTrafficHistory(snapshot)
          }
        } catch {
          // Ignore one bad server push; the next snapshot is independent.
        }
      }
      connection.onclose = () => {
        if (disposed) return
        setSocketConnected(false)
        loadFallbackSnapshot()
        reconnectTimer = window.setTimeout(connect, 2_000)
      }
      connection.onerror = () => connection.close()
    }

    loadFallbackSnapshot()
    connect()
    return () => {
      disposed = true
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      // In React Strict Mode a newly created socket may still be connecting.
      // Close it after it opens, preventing the browser's misleading warning.
      if (socket?.readyState === WebSocket.CONNECTING) {
        socket.onopen = () => socket?.close()
      } else {
        socket?.close()
      }
    }
  }, [isAdmin])

  // Continuous multi-intersection ambulance movement & re-routing progression loop
  useEffect(() => {
    if (!trip || trip.status !== 'active') return undefined

    const path = trip.route.path
    if (path.length <= 1) {
      setTrip((prev) => (prev ? { ...prev, status: 'arrived' } : null))
      return undefined
    }

    const nextNode = path[1]
    const waitSec = signalWaitSeconds(trip.route)
    const travelSec = roadTravelSeconds(trip.route)

    let timer: number | undefined

    if (trip.motionStage === 'waiting_for_signal') {
      const delay = realTimeDelayMilliseconds(Math.max(0.5, waitSec))
      timer = window.setTimeout(() => {
        setTrip((prev) => (prev ? { ...prev, motionStage: 'travelling' } : null))
      }, delay)
    } else if (trip.motionStage === 'travelling') {
      const delay = realTimeDelayMilliseconds(Math.max(0.8, travelSec))
      timer = window.setTimeout(() => {
        const legTotal = waitSec + travelSec
        const historyEntry: RouteHistoryEntry = {
          currentLocation: trip.currentLocation,
          nextLocation: nextNode,
          route: path,
          totalSeconds: legTotal,
          roadTravelSeconds: travelSec,
          signalWaitSeconds: waitSec,
          trafficVersion: trip.route.traffic_version,
          lightPhase: trip.route.segments?.[0]?.source_light_phase,
        }

        setRouteHistory((prev) => [...prev, historyEntry])

        if (nextNode === trip.destination) {
          setTrip((prev) => (prev ? { ...prev, currentLocation: nextNode, status: 'arrived' } : null))
        } else {
          setIsReplanning(true)
          const apiSource = nodeName(nextNode)
          const apiDest = nodeName(trip.destination)

          api
            .post<RouteResponse>('/api/route', {
              start: nextNode,
              end: trip.destination,
              source: apiSource,
              destination: apiDest,
            })
            .then((response) => {
              if (response.data.success !== false) {
                setTrip({
                  currentLocation: nextNode,
                  destination: trip.destination,
                  route: response.data,
                  status: response.data.path.length <= 1 ? 'arrived' : 'active',
                  motionStage: motionStageForRoute(response.data),
                  vehicleType: trip.vehicleType,
                })
              } else {
                const fallbackPath = path.slice(1)
                setTrip({
                  ...trip,
                  currentLocation: nextNode,
                  route: { ...trip.route, path: fallbackPath },
                  status: fallbackPath.length <= 1 ? 'arrived' : 'active',
                  motionStage: 'waiting_for_signal',
                })
              }
            })
            .catch(() => {
              const fallbackPath = path.slice(1)
              setTrip({
                ...trip,
                currentLocation: nextNode,
                route: { ...trip.route, path: fallbackPath },
                status: fallbackPath.length <= 1 ? 'arrived' : 'active',
                motionStage: 'waiting_for_signal',
              })
            })
            .finally(() => {
              setIsReplanning(false)
            })
        }
      }, delay)
    }

    return () => {
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [trip])

  const submitRoute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setRouteError(null)

    const sourceId = Number(start)
    const destinationId = Number(end)

    const displaySource = nodeDisplayName(sourceId)
    const apiSource = nodeName(sourceId)
    const displayDest = nodeDisplayName(destinationId)
    const apiDest = nodeName(destinationId)

    console.log(`[FRONTEND] Display source: ${displaySource}`)
    console.log(`[FRONTEND] API source: ${apiSource}`)
    console.log(`[FRONTEND] Source ID: ${sourceId}`)

    console.log(`[FRONTEND] Display destination: ${displayDest}`)
    console.log(`[FRONTEND] API destination: ${apiDest}`)
    console.log(`[FRONTEND] Destination ID: ${destinationId}`)

    if (!destinationSelected || isNaN(destinationId)) {
      setRouteError('Choose a destination before starting the trip.')
      return
    }

    if (sourceId === destinationId) {
      setRouteError('Current location and destination must be different.')
      return
    }

    console.log('[FRONTEND] Sending route request...')
    setIsRouting(true)

    try {
      const response = await api.post<RouteResponse>('/api/route', {
        start: sourceId,
        end: destinationId,
        source: apiSource,
        destination: apiDest
      })

      if (response.data.simulation_connected === false || response.data.success === false) {
        console.warn('[FRONTEND] Simulation unavailable:', response.data.error)
        setTrip(null)
        setRouteError('Simulation unavailable. Please start the Webots simulation.')
        return
      }

      console.log('[FRONTEND] Simulation result received', response.data)
      console.log('[FRONTEND] Rendering recommended route', response.data.recommended_route)

      setRouteHistory([])
      setTrip({
        currentLocation: sourceId,
        destination: destinationId,
        route: response.data,
        status: response.data.path.length <= 1 ? 'arrived' : 'active',
        motionStage: motionStageForRoute(response.data),
        vehicleType,
      })
      setTrafficStatus((previous) => previous && {
        ...previous,
        traffic_version: response.data.traffic_version ?? previous.traffic_version,
        traffic_age_seconds: response.data.traffic_age_seconds ?? previous.traffic_age_seconds,
        source: response.data.traffic_source ?? previous.source,
      })
    } catch (error) {
      console.error('[FRONTEND] Route error:', error)
      setTrip(null)
      const detail = routeErrorMessage(error)
      setRouteError(detail)
    } finally {
      setIsRouting(false)
    }
  }

  const logout = () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    navigate('/login', { replace: true })
  }

  const cancelTrip = () => {
    const shouldReleaseReservations = Boolean(trip && trip.status !== 'arrived')
    setTrip(null)
    setRouteHistory([])
    setRouteError(null)
    setIsReplanning(false)
    setDestinationSelected(false)
    if (shouldReleaseReservations) {
      // The server identifies the EV from the JWT, so a client cannot cancel
      // another driver's slots. Do not keep a cancelled trip visually active
      // while the MQTT cancellation acknowledgement travels to the edge.
      void api.post<RouteCancellationResponse>('/api/route/cancel')
        .catch(() => {
          setRouteError(
            'Trip ended locally, but the reservation release could not be confirmed. It will expire at the intersection if MQTT remains unavailable.',
          )
        })
    }
  }

  if (!currentUser) {
    return (
      <Box className="dashboard-loading">
        <CircularProgress />
      </Box>
    )
  }

  const statusLabel = isAdmin
    ? socketConnected
      ? trafficStatus?.traffic_stale ? 'Traffic feed stale' : 'Live city feed'
      : 'Reconnecting feed…'
    : trafficStatus?.traffic_stale
      ? 'Traffic feed unavailable'
      : 'EV driver'

  return (
    <Box className="dashboard-shell">
      <AppBar className="dashboard-appbar" color="transparent" elevation={0} position="static">
        <Toolbar>
          <Box sx={{ flexGrow: 1 }}>
            <Typography color="text.primary" sx={{ fontWeight: 800, letterSpacing: '-0.03em' }} variant="h6">
              City Traffic Command
            </Typography>
            <Typography color="text.secondary" variant="caption">
              {isAdmin ? 'Operations monitoring' : 'Emergency vehicle routing'}
            </Typography>
          </Box>
          <Chip
            color={telemetrySeverity(trafficStatus)}
            label={statusLabel}
            size="small"
            sx={{ mr: 1.5 }}
          />
          <Button color="inherit" onClick={logout}>Sign out</Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: { xs: 2, md: 4 } }}>
        {isAdmin ? (
          <AdminDashboard
            congestionTotals={congestionTotals}
          graphData={graphData}
          trafficHistory={trafficHistory}
          traffic={traffic}
            trafficStatus={trafficStatus}
          />
        ) : (
          <DriverDashboard
            currentLocation={currentLocation}
            destinationSelected={destinationSelected}
            end={end}
            isReplanning={isReplanning}
            isRouting={isRouting}
            isTripInProgress={isTripInProgress}
            onCancel={cancelTrip}
            onEndChange={(node) => {
              setEnd(node)
              setDestinationSelected(true)
            }}
            onStartChange={(node) => {
              setStart(node)
              setDestinationSelected(false)
              setTrip(null)
              setRouteHistory([])
              setRouteError(null)
            }}
            onSubmit={submitRoute}
            onVehicleTypeChange={setVehicleType}
            routeError={routeError}
            routeHistory={routeHistory}
            start={start}
            trafficStatus={trafficStatus}
            trip={trip}
            vehicleType={vehicleType}
          />
        )}
      </Container>
    </Box>
  )
}

function StatusMetric({ label, value, tone = 'default' }: {
  label: string
  value: string | number
  tone?: 'default' | 'success' | 'warning' | 'error'
}) {
  const colours = {
    default: 'text.primary',
    success: '#2ECC71',
    warning: '#F39C12',
    error: '#E74C3C',
  }
  return (
    <Paper className="status-metric" elevation={0}>
      <Typography color="text.secondary" variant="caption">{label}</Typography>
      <Typography color={colours[tone]} sx={{ fontWeight: 800, mt: 0.5 }} variant="h6">
        {value}
      </Typography>
    </Paper>
  )
}

function LiveQueueChart({ samples }: { samples: TrafficHistoryPoint[] }) {
  const width = 720
  const height = 190
  const padding = { top: 18, right: 20, bottom: 30, left: 52 }
  const maxQueue = Math.max(20, ...samples.map((sample) => sample.totalQueue))
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const pointFor = (sample: TrafficHistoryPoint, index: number) => ({
    x: padding.left + (samples.length <= 1 ? 0 : (index / (samples.length - 1)) * plotWidth),
    y: padding.top + plotHeight - ((sample.totalQueue / maxQueue) * plotHeight),
  })
  const points = samples.map(pointFor)
  const line = points.map((point) => `${point.x},${point.y}`).join(' ')
  const area = points.length > 0
    ? `${padding.left},${padding.top + plotHeight} ${line} ${points.at(-1)?.x},${padding.top + plotHeight}`
    : ''
  const latest = samples.at(-1)

  return (
    <Paper className="traffic-trend-panel" elevation={0}>
      <Box className="panel-heading">
        <Box>
          <Typography sx={{ fontWeight: 750 }} variant="h6">Live network queue trend</Typography>
          <Typography color="text.secondary" variant="body2">Total queued vehicles across the city · latest 30 simulator updates</Typography>
        </Box>
        <Chip color="primary" label={latest ? `${latest.totalQueue} vehicles now` : 'Collecting data'} size="small" variant="outlined" />
      </Box>
      <Box sx={{ px: { xs: 1.5, md: 3 }, pb: 2.5 }}>
        {samples.length < 2 ? (
          <LinearProgress aria-label="Collecting live queue history" />
        ) : (
          <svg aria-label="Total city queue trend over recent simulator updates" className="traffic-trend-chart" role="img" viewBox={`0 0 ${width} ${height}`}>
            <line className="traffic-trend-axis" x1={padding.left} x2={padding.left} y1={padding.top} y2={padding.top + plotHeight} />
            <line className="traffic-trend-axis" x1={padding.left} x2={width - padding.right} y1={padding.top + plotHeight} y2={padding.top + plotHeight} />
            <line className="traffic-trend-guide" x1={padding.left} x2={width - padding.right} y1={padding.top + (plotHeight / 2)} y2={padding.top + (plotHeight / 2)} />
            <polygon className="traffic-trend-area" points={area} />
            <polyline className="traffic-trend-line" points={line} />
            {points.map((point, index) => (
              <circle className="traffic-trend-point" cx={point.x} cy={point.y} key={samples[index].trafficVersion} r="2.8" />
            ))}
            <text className="traffic-trend-label" x={padding.left - 8} y={padding.top + 4} textAnchor="end">{maxQueue}</text>
            <text className="traffic-trend-label" x={padding.left - 8} y={padding.top + plotHeight + 4} textAnchor="end">0</text>
            <text className="traffic-trend-label" x={(padding.left + width - padding.right) / 2} y={height - 5} textAnchor="middle">Recent simulator updates →</text>
          </svg>
        )}
      </Box>
    </Paper>
  )
}

function trafficMapPin(node: TrafficNode): L.DivIcon {
  const priorityClass = node.preemption_active ? ' traffic-map-pin--priority' : ''
  return L.divIcon({
    className: 'traffic-map-pin-wrapper',
    html: `<span class="traffic-map-pin${priorityClass}" style="--pin-colour:${node.color}"><svg viewBox="0 0 32 42" aria-hidden="true"><path d="M16 1.5C8.8 1.5 3 7.2 3 14.3C3 24 16 39.5 16 39.5S29 24 29 14.3C29 7.2 23.2 1.5 16 1.5Z"/><circle cx="16" cy="14" r="5"/></svg></span>`,
    iconAnchor: [16, 40],
    iconSize: [32, 42],
  })
}

/** A geographic reference view for the existing synthetic 5×5 simulator grid. */
function CoimbatoreTrafficMap({ nodes }: { nodes: TrafficNode[] }) {
  return (
    <MapContainer
      attributionControl
      bounds={COIMBATORE_BOUNDS}
      className="city-map-leaflet"
      maxZoom={18}
      minZoom={12}
      scrollWheelZoom={false}
      zoomControl
    >
      <TileLayer
        attribution={'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}
        maxZoom={19}
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {nodes.map((node) => {
        const position = COIMBATORE_GRID_COORDINATES[node.id]
        if (!position) return null
        return (
          <Marker
            alt={`${node.label}, simulator node ${node.id}`}
            icon={trafficMapPin(node)}
            keyboard
            position={position}
            key={node.id}
          >
            <Tooltip className="traffic-map-label" direction="top" offset={[0, -34]} sticky>
              <strong>{node.label}</strong>
              <span>{node.offline ? `Simulator node #${node.id} · OFFLINE` : `Simulator node #${node.id} · queue ${node.queue_length ?? '—'} · flush ${node.flush_time.toFixed(1)}s`}</span>
            </Tooltip>
          </Marker>
        )
      })}
    </MapContainer>
  )
}

/** Derived on every render from the live snapshot; no mirrored filter state. */
function ReservationStream({ nodes }: { nodes: TrafficNode[] }) {
  const activeReservations = nodes
    .filter((node) => node.preemption_active)
    .sort((first, second) => (first.reservation_end_time ?? Infinity) - (second.reservation_end_time ?? Infinity))

  return (
    <Paper className="reservation-stream-panel" elevation={0}>
      <Box className="panel-heading">
        <Box>
          <Typography sx={{ fontWeight: 800 }} variant="h6">Reservation stream</Typography>
          <Typography color="text.secondary" variant="body2">Live FCFS signal windows from the orchestrator.</Typography>
        </Box>
        <Chip color={activeReservations.length ? 'primary' : 'default'} label={`${activeReservations.length} active`} size="small" />
      </Box>
      <Stack className="reservation-stream-list" spacing={1}>
        {activeReservations.length === 0 ? (
          <Typography className="reservation-stream-empty" color="text.secondary" variant="body2">
            No active reservations. Incoming EV requests will appear here as their signal slots activate.
          </Typography>
        ) : activeReservations.map((node) => (
          <Box className="reservation-stream-entry" key={node.id}>
            <Box>
              <Typography sx={{ fontWeight: 800 }} variant="body2">{nodeDisplayName(node.id)}</Typography>
              <Typography color="text.secondary" variant="caption">
                {node.reservation_ev_id ?? 'EV'} · {preemptionLabel(node)}
              </Typography>
            </Box>
            <Typography className="metric-text" color="primary.main" variant="body2">
              {node.reservation_remaining_ticks ?? 0}s
            </Typography>
          </Box>
        ))}
      </Stack>
    </Paper>
  )
}

function AdminDashboard({
  congestionTotals,
  graphData,
  trafficHistory,
  traffic,
  trafficStatus,
}: {
  congestionTotals: { clear: number; moderate: number; heavy: number; offline: number }
  graphData: { nodes: GraphNode[]; links: GraphLink[] }
  trafficHistory: TrafficHistoryPoint[]
  traffic: TrafficSnapshot | null
  trafficStatus: TrafficStatus | null
}) {
  const [visualizationView, setVisualizationView] = useState<'graph' | 'map'>('graph')
  const [blackoutNode, setBlackoutNode] = useState(0)
  const [isUpdatingBlackout, setIsUpdatingBlackout] = useState(false)
  const [blackoutError, setBlackoutError] = useState<string | null>(null)
  const [uhiOverlayEnabled, setUhiOverlayEnabled] = useState(false)
  const [heatmapData, setHeatmapData] = useState<EnvironmentHeatmapPoint[]>([])
  const [isHeatmapLoading, setIsHeatmapLoading] = useState(false)
  const [heatmapError, setHeatmapError] = useState<string | null>(null)
  const telemetryError = trafficStatus?.ingest_error ?? trafficStatus?.mqtt_error
  const offlineNodes = new Set((traffic?.nodes ?? []).filter((node) => node.offline).map((node) => node.id))
  const isSelectedNodeOffline = offlineNodes.has(blackoutNode)
  const staleMessage = !trafficStatus?.traffic_available
    ? 'Waiting for the intersection simulator to publish its first complete 25-node snapshot.'
    : trafficStatus?.traffic_stale
      ? `The latest simulator snapshot is ${formatAge(trafficStatus.traffic_age_seconds)}. Routing is paused until fresh data arrives.`
      : null
  // These live operational counts intentionally remain derived values rather
  // than useState-managed filtered lists, preventing view/data drift.
  const activeReservationNodes = (traffic?.nodes ?? []).filter((node) => node.preemption_active)
  const activeEvCount = new Set(
    activeReservationNodes.map((node) => node.reservation_ev_id).filter((evId): evId is string => Boolean(evId)),
  ).size
  const systemHealth = trafficStatus?.traffic_stale || offlineNodes.size > 0
    ? 'DEGRADED'
    : trafficStatus?.mqtt_connected
      ? 'NOMINAL'
      : 'CONNECTING'

  useEffect(() => {
    if (!uhiOverlayEnabled) return undefined

    let active = true
    const loadEnvironmentalReadings = async () => {
      setIsHeatmapLoading(true)
      try {
        const response = await api.get<EnvironmentHeatmapPoint[]>('/api/environment/heatmap')
        if (active) {
          setHeatmapData(response.data)
          setHeatmapError(null)
        }
      } catch (error) {
        if (active) setHeatmapError(environmentErrorMessage(error))
      } finally {
        if (active) setIsHeatmapLoading(false)
      }
    }

    void loadEnvironmentalReadings()
    const timer = window.setInterval(() => { void loadEnvironmentalReadings() }, STATUS_POLL_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [uhiOverlayEnabled])

  // These are intentionally derived on every render from the raw endpoint
  // response, rather than mirrored in state. It keeps the canvas overlay in
  // lock-step with the most recently fetched live queue values.
  const heavyEmitters = uhiOverlayEnabled
    ? heatmapData.filter((node) => node.uhi_index > 10)
    : []
  const peakUhiIndex = Math.max(1, ...heavyEmitters.map((node) => node.uhi_index))
  const heatmapByNode = new Map(heavyEmitters.map((node) => [node.node_id, node]))

  const updateBlackout = async () => {
    setIsUpdatingBlackout(true)
    setBlackoutError(null)
    try {
      if (isSelectedNodeOffline) {
        await api.delete(`/api/traffic/nodes/${blackoutNode}/blackout`)
      } else {
        await api.post(`/api/traffic/nodes/${blackoutNode}/blackout`)
      }
    } catch (error) {
      setBlackoutError(routeErrorMessage(error))
    } finally {
      setIsUpdatingBlackout(false)
    }
  }

  return (
    <Stack className="orchestrator-dashboard" spacing={2.5}>
      <Box className="command-title-row">
        <Box>
          <Typography className="command-eyebrow" variant="overline">SPATIO-TEMPORAL ORCHESTRATOR</Typography>
          <Typography sx={{ fontWeight: 850, letterSpacing: '-0.04em' }} variant="h4">City network command</Typography>
          <Typography color="text.secondary" sx={{ mt: 0.5 }}>
            Live signal state, FCFS reservation windows, and queue pressure across the 5×5 city grid.
          </Typography>
        </Box>
        <Chip color={systemHealth === 'NOMINAL' ? 'success' : systemHealth === 'DEGRADED' ? 'warning' : 'default'} label={`SYSTEM ${systemHealth}`} />
      </Box>

      {staleMessage && <Alert severity="warning">{staleMessage}</Alert>}
      {telemetryError && <Alert severity="error">{telemetryError}</Alert>}

      <Box className="orchestrator-layout">
        <Stack className="orchestrator-sidebar" component="aside" spacing={1.5}>
          <Paper className="command-sidebar-card" elevation={0}>
            <Typography className="command-eyebrow" variant="overline">GLOBAL METRICS</Typography>
            <Stack spacing={1.25} sx={{ mt: 1 }}>
              <StatusMetric label="Total EVs active" tone={activeEvCount > 0 ? 'success' : 'default'} value={activeEvCount} />
              <StatusMetric label="System health" tone={systemHealth === 'NOMINAL' ? 'success' : systemHealth === 'DEGRADED' ? 'warning' : 'default'} value={systemHealth} />
              <StatusMetric label="MQTT broker" tone={trafficStatus?.mqtt_connected ? 'success' : 'warning'} value={trafficStatus?.mqtt_connected ? 'ONLINE' : 'RECONNECTING'} />
              <StatusMetric label="Snapshot age" tone={trafficStatus?.traffic_stale ? 'warning' : 'success'} value={formatAge(trafficStatus?.traffic_age_seconds)} />
              <StatusMetric label="Offline nodes" tone={(trafficStatus?.offline_node_count ?? offlineNodes.size) > 0 ? 'error' : 'success'} value={trafficStatus?.offline_node_count ?? offlineNodes.size} />
              <StatusMetric label="Traffic revision" value={`v${trafficStatus?.traffic_version ?? 0}`} />
            </Stack>
          </Paper>

          <Paper className="uhi-overlay-control" elevation={0}>
            <Box>
              <Typography sx={{ fontWeight: 800 }} variant="subtitle1">Environmental layer</Typography>
              <Typography color="text.secondary" variant="body2">
                Queue-derived urban heat and emission pressure.
              </Typography>
            </Box>
            <FormControlLabel
              className="uhi-overlay-switch"
              control={<Switch checked={uhiOverlayEnabled} color="primary" onChange={(event) => setUhiOverlayEnabled(event.target.checked)} />}
              label="Overlay UHI Heatmap"
              labelPlacement="start"
              sx={{ justifyContent: 'space-between', m: 0, width: '100%' }}
            />
            {uhiOverlayEnabled && (
              <Typography className="metric-text" color="text.secondary" variant="caption">
                {isHeatmapLoading ? 'Refreshing environmental readings…' : `${heavyEmitters.length} active heat hotspots`}
              </Typography>
            )}
            {uhiOverlayEnabled && heatmapError && <Alert severity="error">{heatmapError}</Alert>}
          </Paper>

          <Paper className="failure-control-panel" elevation={0}>
            <Box>
              <Typography sx={{ fontWeight: 800 }} variant="subtitle1">Failure simulation</Typography>
              <Typography color="text.secondary" variant="body2">Blackout removes a node from live routing.</Typography>
            </Box>
            <FormControl fullWidth size="small">
              <InputLabel id="blackout-node-label">Intersection</InputLabel>
              <Select label="Intersection" labelId="blackout-node-label" onChange={(event) => setBlackoutNode(Number(event.target.value))} value={blackoutNode}>
                {INTERSECTIONS.map((node) => (
                  <MenuItem key={node} value={node}>{nodeDisplayName(node)}{offlineNodes.has(node) ? ' — offline' : ''}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button color={isSelectedNodeOffline ? 'success' : 'error'} disabled={isUpdatingBlackout} onClick={() => { void updateBlackout() }} variant="contained">
              {isUpdatingBlackout ? 'Updating…' : isSelectedNodeOffline ? 'Restore node' : 'Simulate blackout'}
            </Button>
            {blackoutError && <Alert severity="error">{blackoutError}</Alert>}
          </Paper>
        </Stack>

        <Stack className="orchestrator-main" spacing={2}>
          <Paper className="graph-panel" elevation={0}>
            <Box className="panel-heading">
              <Box>
                <Typography sx={{ fontWeight: 800 }} variant="h6">{visualizationView === 'graph' ? 'Live city graph' : 'Coimbatore location map'}</Typography>
                <Typography color="text.secondary" variant="body2">
                  {visualizationView === 'graph' ? 'Topology, congestion, and operational node state.' : 'Simulator locations on a Central Coimbatore reference map.'}
                </Typography>
              </Box>
              <Chip color={trafficStatus?.source === 'mqtt' ? 'success' : 'default'} label={trafficStatus?.source === 'mqtt' ? 'MQTT LIVE' : 'WAITING FOR MQTT'} size="small" variant="outlined" />
            </Box>
            <Tabs aria-label="Network visualization view" className="network-view-tabs" onChange={(_event, nextView: 'graph' | 'map') => setVisualizationView(nextView)} value={visualizationView}>
              <Tab label="Network graph" value="graph" />
              <Tab label="Location map" value="map" />
            </Tabs>
            {!traffic && <LinearProgress />}
            <Box className="city-map-canvas">
              {visualizationView === 'graph' ? (
                <ForceGraph2D
                  backgroundColor="#0F172A"
                  cooldownTicks={0}
                  enableNodeDrag={false}
                  graphData={graphData}
                  height={540}
                  linkColor={() => 'rgba(148, 163, 184, 0.52)'}
                  linkLabel={(link) => {
                    const edge = link as GraphLink
                    return `Average ${edge.direction ?? 'road'} cost: ${edge.weight.toFixed(1)}s`
                  }}
                  linkWidth={1.4}
                  nodeColor={(node) => (node as GraphNode).color}
                  nodeCanvasObject={(node, context, globalScale) => {
                    const graphNode = node as GraphNode
                    const environmentalReading = heatmapByNode.get(graphNode.id)
                    if (environmentalReading && !graphNode.offline) {
                      const intensity = Math.min(1, environmentalReading.uhi_index / peakUhiIndex)
                      const innerRadius = 4 / globalScale
                      const outerRadius = (20 + (42 * intensity)) / globalScale
                      const aura = context.createRadialGradient(
                        graphNode.x ?? 0,
                        graphNode.y ?? 0,
                        innerRadius,
                        graphNode.x ?? 0,
                        graphNode.y ?? 0,
                        outerRadius,
                      )
                      aura.addColorStop(0, `rgba(255, 0, 255, ${0.18 + (0.36 * intensity)})`)
                      aura.addColorStop(0.48, `rgba(220, 20, 60, ${0.13 + (0.25 * intensity)})`)
                      aura.addColorStop(1, 'rgba(220, 20, 60, 0)')
                      context.save()
                      context.globalCompositeOperation = 'screen'
                      context.fillStyle = aura
                      context.beginPath()
                      context.arc(graphNode.x ?? 0, graphNode.y ?? 0, outerRadius, 0, 2 * Math.PI)
                      context.fill()
                      context.restore()
                    }
                    const radius = 6
                    context.beginPath()
                    context.arc(graphNode.x ?? 0, graphNode.y ?? 0, radius, 0, 2 * Math.PI)
                    context.fillStyle = graphNode.color
                    context.fill()
                    context.lineWidth = 1.4 / globalScale
                    context.strokeStyle = '#E2E8F0'
                    context.stroke()
                    const fontSize = 11 / globalScale
                    context.font = `${fontSize}px Inter, Roboto, sans-serif`
                    context.fillStyle = '#E2E8F0'
                    context.textAlign = 'center'
                    context.textBaseline = 'bottom'
                    context.fillText(graphNode.label, graphNode.x ?? 0, (graphNode.y ?? 0) - radius - (3 / globalScale))
                  }}
                  nodeCanvasObjectMode={() => 'replace'}
                  nodeLabel={(node) => {
                    const trafficNode = node as GraphNode
                    const signal = trafficNode.light_phase ? `${trafficNode.light_phase}${trafficNode.active_direction ? ` · ${trafficNode.active_direction}` : ''}` : 'Signal unavailable'
                    const priority = trafficNode.preemption_active ? `\nEV green wave: ${trafficNode.reserved_axis ?? trafficNode.active_direction ?? '—'} (${trafficNode.reservation_remaining_ticks ?? 0}s remaining)` : ''
                    const availability = trafficNode.offline ? '\nStatus: OFFLINE' : ''
                    return `${trafficNode.label}\nQueue: ${trafficNode.queue_length ?? '—'} vehicles\nPredicted flush: ${trafficNode.flush_time.toFixed(1)}s\n${signal}${priority}${availability}`
                  }}
                  nodeRelSize={6}
                />
              ) : <CoimbatoreTrafficMap nodes={traffic?.nodes ?? []} />}
            </Box>
            <Stack className="graph-legend" direction="row" spacing={2}>
              <LegendItem colour="#2ECC71" label={`Clear (${congestionTotals.clear})`} />
              <LegendItem colour="#F39C12" label={`Moderate (${congestionTotals.moderate})`} />
              <LegendItem colour="#E74C3C" label={`Severe (${congestionTotals.heavy})`} />
              <LegendItem colour="#020617" label={`Offline (${congestionTotals.offline})`} />
            </Stack>
          </Paper>
          <LiveQueueChart samples={trafficHistory} />
        </Stack>

        <Stack className="orchestrator-right" component="aside" spacing={2}>
          <ReservationStream nodes={traffic?.nodes ?? []} />
          <Paper className="telemetry-panel" elevation={0}>
            <Box className="panel-heading">
              <Box>
                <Typography sx={{ fontWeight: 800 }} variant="h6">Intersection telemetry</Typography>
                <Typography color="text.secondary" variant="body2">Most recent edge readings.</Typography>
              </Box>
            </Box>
            <TableContainer sx={{ maxHeight: 390 }}>
              <Table size="small" stickyHeader>
                <TableHead><TableRow><TableCell>Node</TableCell><TableCell align="right">Queue</TableCell><TableCell align="right">Flush</TableCell><TableCell>Signal</TableCell></TableRow></TableHead>
                <TableBody>
                  {(traffic?.nodes ?? []).map((node) => (
                    <TableRow hover key={node.id}>
                      <TableCell>{nodeDisplayName(node.id)}</TableCell>
                      <TableCell align="right" className="metric-text">{node.queue_length ?? '—'}</TableCell>
                      <TableCell align="right" className="metric-text">{node.flush_time.toFixed(1)}s</TableCell>
                      <TableCell><Chip color={node.offline ? 'error' : node.preemption_active ? 'primary' : node.light_phase === 'YELLOW' ? 'warning' : 'success'} label={node.offline ? 'OFFLINE' : node.preemption_active ? preemptionLabel(node) : node.light_phase === 'YELLOW' ? `Y · ${node.active_direction}` : node.active_direction ?? '—'} size="small" variant="outlined" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Stack>
      </Box>
    </Stack>
  )
}

function LegendItem({ colour, label }: { colour: string; label: string }) {
  return (
    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
      <Box sx={{ backgroundColor: colour, borderRadius: '50%', height: 9, width: 9 }} />
      <Typography color="text.secondary" variant="caption">{label}</Typography>
    </Stack>
  )
}

/** A small visual companion to the existing textual live-trip status. */
function EvTripMap({ trip }: { trip: ActiveTrip }) {
  const nextNode = trip.status === 'active' ? trip.route.path[1] : undefined
  const currentPoint = mapCoordinate(trip.currentLocation)
  const destinationPoint = mapCoordinate(trip.destination)
  const isTravelling = trip.status === 'active' && trip.motionStage === 'travelling' && nextNode !== undefined
  const nextPoint = nextNode === undefined ? currentPoint : mapCoordinate(nextNode)
  const animationDuration = Math.max(400, realTimeDelayMilliseconds(roadTravelSeconds(trip.route)))
  const routePoints = trip.route.path.map((node) => {
    const point = mapCoordinate(node)
    return `${point.x},${point.y}`
  }).join(' ')

  return (
    <Box sx={{ mt: 2.5 }}>
      <Box sx={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography sx={{ fontWeight: 750 }} variant="subtitle1">Ambulance movement</Typography>
        <Typography color="text.secondary" variant="caption">
          {trip.status === 'arrived'
            ? 'Destination reached'
            : isTravelling
              ? `Moving to ${nodeDisplayName(nextNode)}`
              : `At ${nodeDisplayName(trip.currentLocation)}`}
        </Typography>
      </Box>
      <Box
        aria-label={`Virtual city map: ${emergencyVehicleLabel(trip.vehicleType)} at ${nodeDisplayName(trip.currentLocation)}`}
        className="ev-trip-map"
        role="img"
      >
          <svg aria-hidden="true" viewBox={`0 0 ${MAP_VIEWBOX_WIDTH} ${MAP_VIEWBOX_HEIGHT}`}>
          {CITY_GRID_ROADS.map(([source, target]) => {
            const from = mapCoordinate(source)
            const to = mapCoordinate(target)
            return (
              <line
                className="ev-trip-map-road"
                key={`${source}-${target}`}
                x1={from.x}
                x2={to.x}
                y1={from.y}
                y2={to.y}
              />
            )
          })}
          {trip.route.path.length > 1 && (
            <polyline className="ev-trip-map-route" points={routePoints} />
          )}
          {INTERSECTIONS.map((node) => {
            const point = mapCoordinate(node)
            const isCurrent = node === trip.currentLocation
            const isDestination = node === trip.destination
            const isOnRoute = trip.route.path.includes(node)
            return (
              <circle
                className={isDestination ? 'ev-trip-map-node destination' : isCurrent ? 'ev-trip-map-node current' : isOnRoute ? 'ev-trip-map-node route' : 'ev-trip-map-node'}
                cx={point.x}
                cy={point.y}
                key={node}
                r={isDestination || isCurrent ? 3.7 : 2.1}
              />
            )
          })}
          <text className="ev-trip-map-label" x={destinationPoint.x} y={destinationPoint.y + 1.2}>D</text>
          {isTravelling ? (
            <g className="ev-trip-map-ambulance" key={`moving-${trip.currentLocation}-${nextNode}`}>
              <animateTransform
                attributeName="transform"
                dur={`${animationDuration}ms`}
                fill="freeze"
                from={`${currentPoint.x} ${currentPoint.y}`}
                to={`${nextPoint.x} ${nextPoint.y}`}
                type="translate"
              />
              <text dominantBaseline="central" fontSize="6.5" textAnchor="middle" x="0" y="0">{emergencyVehicleEmoji(trip.vehicleType)}</text>
            </g>
          ) : (
            <g className="ev-trip-map-ambulance" transform={`translate(${currentPoint.x} ${currentPoint.y})`}>
              <text dominantBaseline="central" fontSize="6.5" textAnchor="middle" x="0" y="0">{emergencyVehicleEmoji(trip.vehicleType)}</text>
            </g>
          )}
        </svg>
      </Box>
      <Typography color="text.secondary" sx={{ display: 'block', mt: 1 }} variant="caption">
        Blue route is recalculated at every intersection. The selected emergency vehicle waits at a signal, then moves along the highlighted next road leg.
      </Typography>
    </Box>
  )
}

function DriverDashboard({
  currentLocation,
  destinationSelected,
  end,
  isReplanning,
  isRouting,
  isTripInProgress,
  onCancel,
  onEndChange,
  onStartChange,
  onSubmit,
  onVehicleTypeChange,
  routeError,
  routeHistory,
  start,
  trafficStatus,
  trip,
  vehicleType,
}: {
  currentLocation: number
  destinationSelected: boolean
  end: number
  isReplanning: boolean
  isRouting: boolean
  isTripInProgress: boolean
  onCancel: () => void
  onEndChange: (node: number) => void
  onStartChange: (node: number) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onVehicleTypeChange: (vehicleType: EmergencyVehicleType) => void
  routeError: string | null
  routeHistory: RouteHistoryEntry[]
  start: number
  trafficStatus: TrafficStatus | null
  trip: ActiveTrip | null
  vehicleType: EmergencyVehicleType
}) {
  const upcomingSegment = trip ? latestSegment(trip.route) : undefined
  const upcomingReservation = reservationWindowLabel(upcomingSegment)
  const grantedReservations = trip?.route.reservations?.filter((reservation) => reservation.granted).length ?? 0
  const completedTripSeconds = routeHistory.reduce(
    (total, entry) => total + entry.totalSeconds,
    0,
  )
  const projectedTripSeconds = completedTripSeconds + (trip?.route.eta_seconds ?? 0)
  const recommendedHospitals = nearestHospitalNodes(start)
  const telemetryMessage = trafficStatus?.traffic_stale
    ? 'Live traffic is stale. New route requests will resume when the intersection feed is fresh.'
    : !trafficStatus?.reservation_control_ready
      ? 'Live traffic is available, but the intersection reservation controller is still starting. Restart the updated intersection agent if this does not clear.'
      : `Live routing telemetry: ${trafficStatus?.source ?? 'connecting'} · ${formatAge(trafficStatus?.traffic_age_seconds)}.`
  const currentTarget = trip ? trip.destination : destinationSelected ? end : null
  const liveEta = trip ? `${trip.route.eta_seconds.toFixed(1)}s` : '—'

  return (
    <Stack className="driver-dashboard" spacing={3}>
      <Paper className="driver-command-header" elevation={0}>
        <Box>
          <Typography className="command-eyebrow" variant="overline">EV AGENT · LIVE PRIORITY CONTROL</Typography>
          <Typography sx={{ fontWeight: 850, letterSpacing: '-0.04em' }} variant="h4">
            {emergencyVehicleEmoji(vehicleType)} {emergencyVehicleLabel(vehicleType)} navigation
          </Typography>
        </Box>
        <Stack className="driver-command-metrics" direction={{ xs: 'column', sm: 'row' }} spacing={{ xs: 1.5, sm: 4 }}>
          <Box>
            <Typography className="command-eyebrow" variant="overline">CURRENT ROUTE TARGET</Typography>
            <Typography sx={{ fontWeight: 800 }} variant="h6">{currentTarget === null ? 'SELECT DESTINATION' : nodeDisplayName(currentTarget)}</Typography>
          </Box>
          <Box>
            <Typography className="command-eyebrow" variant="overline">LIVE ETA</Typography>
            <Typography className="driver-live-eta" color="primary.main">{liveEta}</Typography>
          </Box>
        </Stack>
      </Paper>

      <Grid container spacing={3}>
      <Grid size={{ xs: 12, lg: 5 }}>
        <Paper className="route-form-panel" elevation={0}>
          <Typography sx={{ fontWeight: 800 }} variant="h5">Emergency route</Typography>
          <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
            The vehicle requests a fresh shortest route after every intersection, using the latest live traffic and signal state.
          </Typography>

          <Alert severity={telemetrySeverity(trafficStatus)} sx={{ mt: 2.5 }}>
            {telemetryMessage}
          </Alert>

          <Box component="form" onSubmit={onSubmit} sx={{ mt: 2 }}>
            <FormControl fullWidth margin="normal">
              <InputLabel id="vehicle-type-label">Emergency vehicle</InputLabel>
              <Select
                disabled={isTripInProgress}
                label="Emergency vehicle"
                labelId="vehicle-type-label"
                onChange={(event) => onVehicleTypeChange(event.target.value as EmergencyVehicleType)}
                value={vehicleType}
              >
                {EMERGENCY_VEHICLES.map((vehicle) => (
                  <MenuItem key={vehicle.value} value={vehicle.value}>{emergencyVehicleEmoji(vehicle.value)} {vehicle.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel id="start-node-label">Current location</InputLabel>
              <Select
                disabled={isTripInProgress}
                label="Current location"
                labelId="start-node-label"
                onChange={(event) => onStartChange(Number(event.target.value))}
                value={start}
              >
                {INTERSECTIONS.map((node) => <MenuItem key={node} value={node}>{nodeDisplayName(node)}</MenuItem>)}
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel id="end-node-label">Destination</InputLabel>
              <Select
                disabled={isTripInProgress}
                label="Destination"
                labelId="end-node-label"
                onChange={(event) => onEndChange(Number(event.target.value))}
                value={destinationSelected ? end : ''}
              >
                <MenuItem disabled value="">Choose a destination</MenuItem>
                {INTERSECTIONS.map((node) => <MenuItem key={node} value={node}>{nodeDisplayName(node)}</MenuItem>)}
              </Select>
            </FormControl>
            {!destinationSelected && !isTripInProgress && (
              <Box sx={{ background: '#f0fdf4', border: '1px solid rgba(22, 163, 74, 0.2)', borderRadius: 2, mt: 1.5, p: 1.5 }}>
                <Typography sx={{ fontWeight: 700 }} variant="body2">Recommended nearby hospitals</Typography>
                <Typography color="text.secondary" sx={{ display: 'block', mb: 1, mt: 0.25 }} variant="caption">
                  Based on the current simulated location. Select one to use it as your destination.
                </Typography>
                <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.75 }}>
                  {recommendedHospitals.map((hospital) => (
                    <Chip
                      clickable
                      color="success"
                      key={hospital}
                      label={`${nodeDisplayName(hospital)} · ${gridDistance(start, hospital)} junctions`}
                      onClick={() => onEndChange(hospital)}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                </Stack>
              </Box>
            )}
            <Button className="driver-priority-action" disabled={isRouting || isTripInProgress || !destinationSelected} fullWidth size="large" sx={{ mt: 2 }} type="submit" variant="contained">
              {isRouting
                ? 'ANALYZING TRAFFIC IN WEBOTS…'
                : isTripInProgress
                  ? 'TRIP IN PROGRESS'
                  : !destinationSelected
                    ? 'CHOOSE A DESTINATION'
                    : 'REQUEST PRIORITY ROUTE'}
            </Button>
            {isTripInProgress && (
              <Button color="inherit" fullWidth onClick={onCancel} sx={{ mt: 1 }} variant="text">
                End active trip
              </Button>
            )}
          </Box>
          {routeError && <Alert severity="error" sx={{ mt: 2 }}>{routeError}</Alert>}
        </Paper>
      </Grid>

      <Grid size={{ xs: 12, lg: 7 }}>
        <Paper className="trip-panel" elevation={0}>
          <Box className="panel-heading">
            <Box>
              <Typography sx={{ fontWeight: 800 }} variant="h5">Live trip status</Typography>
              <Typography color="text.secondary" variant="body2">
                Position updates when the vehicle reaches each intersection.
              </Typography>
            </Box>
            <Chip color={trip?.status === 'arrived' ? 'success' : 'primary'} label={`Current: ${nodeDisplayName(currentLocation)}`} />
          </Box>

          <Divider />

          {!trip ? (
            <Alert severity="info" sx={{ mt: 3 }}>
              Choose the {emergencyVehicleLabel(vehicleType).toLowerCase()}’s current location and destination, then start the trip. The route will be recalculated at every junction.
            </Alert>
          ) : (
            <Stack spacing={2.5} sx={{ mt: 3 }}>
              <Alert severity={trip.status === 'arrived' ? 'success' : 'info'}>
                {trip.status === 'arrived'
                  ? `Destination reached: ${nodeDisplayName(trip.destination)}.`
                  : trip.status === 'retrying' || isReplanning
                    ? 'Reached an intersection. Requesting a fresh path from the current position…'
                    : trip.motionStage === 'waiting_for_signal'
                      ? `Waiting at ${nodeDisplayName(trip.currentLocation)} for the ${upcomingSegment?.direction ?? 'next'} signal movement. The ${signalWaitSeconds(trip.route).toFixed(1)}-second signal wait is included in the arrival estimate.${upcomingReservation ? ' The FCFS reservation is secured.' : ''}`
                    : `Current ETA from ${nodeDisplayName(trip.currentLocation)}: ${trip.route.eta_seconds.toFixed(1)} seconds.`}
              </Alert>

              <Box>
                <Typography sx={{ fontWeight: 750 }} variant="subtitle1">
                  {trip.status === 'arrived' ? 'Trip complete' : 'Current shortest route'}
                </Typography>
                <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, mt: 1.25 }}>
                  {trip.route.path.map((node, index) => (
                    <Chip
                      color={index === 0 ? 'primary' : index === trip.route.path.length - 1 ? 'success' : 'default'}
                      key={`${node}-${index}`}
                      label={index === trip.route.path.length - 1 ? `Destination: ${nodeDisplayName(node)}` : nodeDisplayName(node)}
                      variant={index === 0 ? 'filled' : 'outlined'}
                    />
                  ))}
                  {trip.route.recommended_route && (
                    <Box sx={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 2, p: 2, mt: 1.5 }}>
                      <Typography sx={{ fontWeight: 800, color: '#0f172a' }} variant="subtitle2">
                        WEBOTS SIMULATION TRAFFIC ANALYSIS
                      </Typography>
                      <Stack direction="row" spacing={2} sx={{ mt: 1, mb: 1.5 }}>
                        <Chip color={trip.route.traffic_level === 'HIGH' ? 'error' : trip.route.traffic_level === 'MODERATE' ? 'warning' : 'success'} label={`Traffic: ${trip.route.traffic_level ?? 'LOW'}`} size="small" />
                        <Chip color="primary" label={`ETA: ${trip.route.eta_minutes ? trip.route.eta_minutes.toFixed(1) + ' min' : (trip.route.eta_seconds / 60).toFixed(1) + ' min'}`} size="small" />
                        <Chip label={`Status: ${trip.route.simulation_status ?? 'completed'}`} size="small" variant="outlined" />
                      </Stack>
                      <Typography color="text.secondary" sx={{ fontStyle: 'italic', mb: 1 }} variant="body2">
                        Reason: {trip.route.reason ?? 'Lowest predicted congestion route selected'}
                      </Typography>
                      <Typography sx={{ fontWeight: 700 }} variant="caption">RECOMMENDED SIMULATION ROUTE:</Typography>
                      <Typography sx={{ fontFamily: 'monospace', fontWeight: 600, color: '#1e293b', mt: 0.25 }} variant="body2">
                        {trip.route.recommended_route.join(' → ')}
                      </Typography>
                    </Box>
                  )}
                </Stack>
              </Box>

              <EvTripMap trip={trip} />

              {upcomingSegment && trip.status !== 'arrived' && (
                <Paper className="next-leg-card driver-next-instruction" elevation={0}>
                  <Typography color="text.secondary" variant="caption">
                    {trip.motionStage === 'waiting_for_signal' ? 'SIGNAL WAIT' : 'NEXT IMMEDIATE TURN'}
                  </Typography>
                  <Typography sx={{ fontWeight: 850, mt: 0.5 }} variant="h5">
                    {nodeDisplayName(upcomingSegment.from)} → {nodeDisplayName(upcomingSegment.to)} · {upcomingSegment.direction}
                  </Typography>
                  <Typography color="text.secondary" sx={{ mt: 0.5 }} variant="body2">
                    {upcomingSegment.source_light_phase} {upcomingSegment.source_active_direction ? `(${upcomingSegment.source_active_direction})` : ''} · signal wait {signalWaitSeconds(trip.route).toFixed(1)}s · road travel {roadTravelSeconds(trip.route).toFixed(1)}s · total leg {upcomingSegment.travel_cost?.toFixed(1) ?? '—'}s
                  </Typography>
                  {upcomingReservation && (
                    <Typography color="primary.main" sx={{ fontWeight: 650, mt: 0.75 }} variant="body2">
                      {upcomingReservation}
                    </Typography>
                  )}
                </Paper>
              )}

              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                <Chip label={`Vehicle: ${emergencyVehicleEmoji(trip.vehicleType)} ${emergencyVehicleLabel(trip.vehicleType)}`} variant="outlined" />
                <Chip label={`Traffic revision: v${trip.route.traffic_version ?? '—'}`} variant="outlined" />
                <Chip label={`Telemetry used: ${formatAge(trip.route.traffic_age_seconds)}`} variant="outlined" />
                <Chip
                  color={trip.route.reservation_status?.startsWith('granted') ? 'primary' : 'default'}
                  label={`FCFS slots: ${grantedReservations} · ${trip.route.reservation_status ?? 'pending'}`}
                  variant="outlined"
                />
                <Chip label={`Estimated total trip time: ${projectedTripSeconds.toFixed(1)}s`} variant="outlined" />
              </Stack>
            </Stack>
          )}
        </Paper>
      </Grid>

      {routeHistory.length > 0 && (
        <Grid size={12}>
          <Paper className="route-history-panel" elevation={0}>
            <Box className="panel-heading">
              <Box>
                <Typography sx={{ fontWeight: 750 }} variant="h6">Re-routing history</Typography>
                <Typography color="text.secondary" variant="body2">Each leg is followed by a new live shortest-path calculation.</Typography>
              </Box>
            </Box>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>From</TableCell>
                    <TableCell>Moved to</TableCell>
                    <TableCell>Route received at this node</TableCell>
                    <TableCell align="right">Wait</TableCell>
                    <TableCell align="right">Road</TableCell>
                    <TableCell align="right">Leg total</TableCell>
                    <TableCell>Signal state</TableCell>
                    <TableCell align="right">Traffic rev.</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {routeHistory.map((entry, index) => (
                    <TableRow key={`${entry.currentLocation}-${entry.nextLocation}-${index}`}>
                      <TableCell>{nodeDisplayName(entry.currentLocation)}</TableCell>
                      <TableCell>{nodeDisplayName(entry.nextLocation)}</TableCell>
                      <TableCell>{entry.route.map(nodeDisplayName).join(' → ')}</TableCell>
                      <TableCell align="right">{entry.signalWaitSeconds.toFixed(1)}s</TableCell>
                      <TableCell align="right">{entry.roadTravelSeconds.toFixed(1)}s</TableCell>
                      <TableCell align="right">{entry.totalSeconds.toFixed(1)}s</TableCell>
                      <TableCell>{entry.lightPhase ?? '—'}</TableCell>
                      <TableCell align="right">v{entry.trafficVersion ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
      )}
      </Grid>
    </Stack>
  )
}
