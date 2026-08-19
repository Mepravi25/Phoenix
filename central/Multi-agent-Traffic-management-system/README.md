# City Traffic Command

The React/FastAPI application is now the primary application. The Python
intersection simulator is an edge-data producer; FastAPI is the MQTT-backed
orchestrator; React is the administrator and EV-driver interface.

```text
intersection_agent.py ── MQTT traffic telemetry ──> FastAPI ── WebSocket/API ──> React
       queue, phase, reservations                 route/auth                    dashboards
         ^                 |                          |
         |  reserve/cancel |                          | FCFS booking before route reply
         └─────────────────┴──── MQTT acknowledgements ┘
```

`orchestrator_dashboard.py` and `ev_agent.py` are retained as Streamlit-era
development prototypes. Do not run them alongside this production-style path:
their responsibilities now live in `backend/main.py` and the React driver
view.

## What each role sees

- An `admin` account sees a monitoring-only city network: live graph, queue,
  congestion, signal phase, MQTT connection, and data freshness.
- An `ev_driver` account can start an emergency trip. At every simulated
  intersection, the dashboard asks FastAPI for a new signal-aware route from
  the vehicle’s current location, rather than continuing the original route.

Each EV-driver account receives a stable, server-side EV identity. Before a
route is returned, FastAPI requests short FCFS signal windows from the edge
intersections along its near-term path. A conflicting later request is either
rerouted around the conflicting downstream node or assigned a later departure
window at its current node. A booked window temporarily holds green only at
that immediate junction, then the controller clears through yellow and resumes
its normal cycle. Ending a trip releases the driver’s remaining bookings.

FastAPI will reject route requests when the MQTT data is missing or older than
eight seconds. This prevents the app from silently routing on made-up traffic.

## First-time setup

Use a Python environment that supports the packages in
[`requirements.txt`](requirements.txt). From the project folder, install the
Python dependencies and the React dependencies:

```cmd
python -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

Create `backend/.env` from [`.env.example`](.env.example), setting a real
`DATABASE_URL` and a long `JWT_SECRET_KEY`. Keep those values private.

## Run locally on Windows CMD

Open three terminals. All commands below use the same local Mosquitto broker.
If `mosquitto -v` reports that port `1883` is already in use, the Mosquitto
Windows service is already running—leave it running and do not start a second
broker.

### 1. Start the live intersection simulator

```cmd
cd /d "C:\Users\Faqrudeen Faizan Z\PhoenixHacks"
set "MQTT_BROKER=127.0.0.1"
set "MQTT_PORT=1883"
set "MQTT_TRANSPORT=tcp"
set "SIMULATION_LOG_INTERVAL_TICKS=5"
set "SIMULATION_LOG_JSON=0"
python intersection_agent.py
```

The terminal prints a five-by-five queue grid, five-by-five predicted flush
time grid, active signal-phase counts, and its MQTT connection state. Set
`SIMULATION_LOG_JSON=1` to also print the complete JSON payload; set
`SIMULATION_LOG_INTERVAL_TICKS=1` to see every simulated second.

Wait until the simulator prints this before requesting an EV route:

```text
[reservation] Controller ready: listening for reserve and cancel commands.
```

After changing `intersection_agent.py`, stop it with `Ctrl+C` and start it
again—the simulator is a long-running process and does not hot-reload code.

### 2. Start FastAPI—the MQTT orchestrator

```cmd
cd /d "C:\Users\Faqrudeen Faizan Z\PhoenixHacks"
set "MQTT_BROKER=127.0.0.1"
set "MQTT_PORT=1883"
set "MQTT_TRANSPORT=tcp"
set "TRAFFIC_DEMO_MODE=0"
python -m uvicorn backend.main:app --reload --port 8000
```

FastAPI subscribes to `city/intersections/update` and
`city/intersections/reserve/response`. It publishes reservation requests and
cancellations to the edge controller only after an EV driver requests a route.
Visit
`http://localhost:8000/health` to verify the MQTT state, latest simulation
tick, data age, active pre-emptions, reservation-control status, and ingest
errors. The service receives a retained snapshot immediately when the
simulator is already running.

### 3. Start the React dashboard

```cmd
cd /d "C:\Users\Faqrudeen Faizan Z\PhoenixHacks\frontend"
set "VITE_API_BASE_URL=http://localhost:8000"
npm run dev
```

Open `http://localhost:5173`. The WebSocket URL is derived from the API URL;
set `VITE_TRAFFIC_WS_URL` only when a deployment uses a separate WebSocket
host.

## Useful environment settings

| Variable | Purpose |
| --- | --- |
| `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TRANSPORT` | Must match in the simulator and FastAPI terminal sessions. |
| `SIMULATION_LOG_INTERVAL_TICKS` | Console grid-summary interval; `0` disables it. |
| `SIMULATION_LOG_JSON` | Set to `1` to print the full simulator JSON records. |
| `TRAFFIC_STALE_AFTER_SECONDS` | Maximum accepted age of a live MQTT snapshot (default `8`). |
| `TRAFFIC_DEMO_MODE` | Set to `1` only for a no-MQTT visual demo; normal operation uses `0`. |
| `RESERVATION_HORIZON_SECONDS` | FCFS timeline length owned by each intersection (default `120`). |
| `RESERVATION_WINDOW_SECONDS` | Short green-wave booking length (default `4`). |
| `RESERVATION_LEAD_SECONDS` | Minimum time before the first booking begins (default `2`). |
| `RESERVATION_ACK_TIMEOUT_SECONDS` | Per-intersection acknowledgement limit (default `2.5`). |
| `RESERVATION_ACK_ATTEMPTS` | Idempotent MQTT reservation publishes before reporting an unavailable controller (default `2`). |
| `RESERVATION_MAX_REROUTES` | Maximum downstream-conflict reroutes before returning `409` (default `3`). |
| `VITE_EV_SECONDS_PER_ETA_SECOND` | Real seconds per simulated second for the EV dashboard (default `1`, which keeps vehicle movement aligned with the traffic-light ticks). Lower only for an intentionally accelerated demo. |

The reservation MQTT messages preserve the requested core fields (`node`,
`ev_id`, `start_time`, and `duration`) and add `axis`, `request_id`, and
`reservation_id`. The additions are necessary to select a safe N/S or E/W
green and to make QoS-1 request/cancel delivery idempotent.

## Admin account

Self-registration deliberately creates an `ev_driver`, which prevents someone
from granting themselves monitoring privileges. Promote a known user using
your existing PostgreSQL administration workflow, then sign out and sign in
again so the JWT carries the new role:

```sql
UPDATE users SET role = 'admin' WHERE username = 'your-admin-username';
```
