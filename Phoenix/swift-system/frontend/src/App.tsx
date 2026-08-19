import React, { useEffect, useState } from 'react';
import { Activity, ShieldAlert, Zap, Radio, RefreshCw, Cpu } from 'lucide-react';
import { LiveMap } from './components/LiveMap';
import { RouteEtaCard } from './components/RouteEtaCard';
import { SignalGrid } from './components/SignalGrid';
import { MetricsComparison } from './components/MetricsComparison';
import { ControlPanel } from './components/ControlPanel';
import { AlertAuditStream } from './components/AlertAuditStream';
import { EmergencyStatusCard } from './components/EmergencyStatusCard';

export function App() {
  const [telemetry, setTelemetry] = useState<any>(null);
  const [orchestration, setOrchestration] = useState<any>(null);
  const [decision, setDecision] = useState<any>(null);
  const [connected, setConnected] = useState<boolean>(false);
  const [loadingEmergency, setLoadingEmergency] = useState<boolean>(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWS = () => {
      ws = new WebSocket('ws://localhost:8000/ws');

      ws.onopen = () => {
        setConnected(true);
        console.log('Connected to SWIFT WebSocket Hub');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'TELEMETRY') {
            setTelemetry(data.telemetry);
            setOrchestration(data.orchestration);
            if (data.decision) {
              setDecision(data.decision);
            }
          }
        } catch (e) {
          console.error('Error parsing WS frame:', e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimeout = setTimeout(connectWS, 2000);
      };

      ws.onerror = () => {
        setConnected(false);
      };
    };

    connectWS();

    // Initial state fetch
    fetch('http://localhost:8000/api/state')
      .then(res => res.json())
      .then(data => {
        if (data.decision) setDecision(data.decision);
      })
      .catch(err => console.error('Initial state fetch error:', err));

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  const handleTriggerEmergency = async () => {
    setLoadingEmergency(true);
    try {
      const res = await fetch('http://localhost:8000/api/emergency/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event: 'EMERGENCY_REQUEST',
          ambulance_id: 'AMB_01',
          emergency_level: 'CRITICAL',
          current_node: 12
        })
      });
      const data = await res.json();
      setDecision(data);
      console.log('Emergency request authorized:', data);
    } catch (e) {
      console.error('Error triggering emergency:', e);
    } finally {
      setLoadingEmergency(false);
    }
  };

  const handleToggleMode = async (mode: string) => {
    try {
      await fetch('http://localhost:8000/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
    } catch (e) {
      console.error('Error toggling mode:', e);
    }
  };

  const handleInjectIncident = async (road_id: string) => {
    try {
      await fetch('http://localhost:8000/api/incident', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ road_id, type: 'ACCIDENT', severity: 'HIGH' })
      });
    } catch (e) {
      console.error('Error injecting incident:', e);
    }
  };

  const handleClearIncidents = async () => {
    try {
      await fetch('http://localhost:8000/api/incident', { method: 'DELETE' });
    } catch (e) {
      console.error('Error clearing incidents:', e);
    }
  };

  const handleSetTrafficProfile = async (profile: string) => {
    try {
      await fetch('http://localhost:8000/api/traffic-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile })
      });
    } catch (e) {
      console.error('Error setting profile:', e);
    }
  };

  const activeRoute = decision?.route?.map((n: number) => `Node ${n}`) || orchestration?.active_route || telemetry?.ambulance?.route || ['Node 12', 'Node 13', 'Node 14', 'Node 19'];
  const mode = telemetry?.mode || 'SWIFT';
  const incidents = telemetry?.incidents || {};
  const nodes25 = telemetry?.nodes_25 || [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 lg:p-6 space-y-6">
      {/* Header Bar */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 glass-panel p-4 rounded-2xl border border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Zap className="w-6 h-6 fill-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-black text-white tracking-wide flex items-center gap-2">
              SWIFT SYSTEM
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                v1.0 MASTER
              </span>
            </h1>
            <p className="text-xs text-slate-400 font-medium">Simulation-Side Telemetry & Central Emergency Decision Orchestrator</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border ${connected ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400 animate-pulse'}`}>
            <Radio className="w-3.5 h-3.5" />
            {connected ? '25-Node Telemetry Stream Active' : 'Connecting to Server...'}
          </div>
        </div>
      </header>

      {/* Emergency Status & Hospital Decision Banner */}
      <EmergencyStatusCard
        decision={decision}
        telemetry={telemetry}
        onTriggerEmergency={handleTriggerEmergency}
        isLoadingEmergency={loadingEmergency}
      />

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: 25-Node Signal Control Grid & Live Map (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <SignalGrid junctions={telemetry?.junctions || {}} nodes25={nodes25} decision={decision} />
          <LiveMap telemetry={telemetry} activeRoute={activeRoute} />
        </div>

        {/* Right Column: Route ETA, Command Panel, Audit Stream (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <RouteEtaCard ambulance={telemetry?.ambulance} activeRoute={activeRoute} mode={mode} />
          <ControlPanel
            mode={mode}
            onToggleMode={handleToggleMode}
            onInjectIncident={handleInjectIncident}
            onClearIncidents={handleClearIncidents}
            onSetTrafficProfile={handleSetTrafficProfile}
            hasIncidents={Object.keys(incidents).length > 0}
          />
          <AlertAuditStream orchestration={orchestration} incidents={incidents} />
          <MetricsComparison telemetry={telemetry} />
        </div>
      </div>
    </div>
  );
}

export default App;
