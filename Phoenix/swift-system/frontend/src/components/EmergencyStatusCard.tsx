import React from 'react';
import { Siren, Building2, Route as RouteIcon, Clock, CheckCircle, ShieldAlert } from 'lucide-react';

interface EmergencyStatusCardProps {
  decision: any;
  telemetry: any;
  onTriggerEmergency: () => void;
  isLoadingEmergency?: boolean;
}

export const EmergencyStatusCard: React.FC<EmergencyStatusCardProps> = ({
  decision,
  telemetry,
  onTriggerEmergency,
  isLoadingEmergency = false
}) => {
  const hospital = decision?.selected_hospital;
  const route = decision?.route || [];
  const status = decision?.status || 'IDLE';
  const isAuthorized = status === 'ROUTE_AUTHORIZED';
  const tick = telemetry?.nodes_25?.[0]?.simulation_tick || telemetry?.simulation_tick || 105;

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
      {/* Header & Demo Trigger */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400">
            <Siren className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white tracking-wide">EMERGENCY ROUTE & HOSPITAL DISPATCH</h2>
            <p className="text-xs text-slate-400">Central Server Decision Orchestrator</p>
          </div>
        </div>

        <button
          onClick={onTriggerEmergency}
          disabled={isLoadingEmergency}
          className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-rose-950/50 transition-all cursor-pointer active:scale-95 disabled:opacity-50"
        >
          <ShieldAlert className="w-4 h-4" />
          {isLoadingEmergency ? 'RESERVING CORRIDOR...' : 'TRIGGER EMERGENCY'}
        </button>
      </div>

      {/* Emergency Status Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Hospital Card */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Building2 className="w-4 h-4 text-cyan-400" /> Nearest Government Hospital
          </div>
          <div className="text-sm font-bold text-white">
            {hospital ? hospital.name : 'Rajiv Gandhi Government General Hospital'}
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Type: {hospital?.type || 'Government'}</span>
            <span className="text-cyan-400 font-bold">{hospital?.distance_km ? `${hospital.distance_km} km` : '2.4 km'}</span>
          </div>
        </div>

        {/* Corridor Active Card */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
            <span className="flex items-center gap-2"><RouteIcon className="w-4 h-4 text-emerald-400" /> Green Corridor</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${isAuthorized ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-slate-800 text-slate-400'}`}>
              {isAuthorized ? 'ACTIVE' : 'IDLE'}
            </span>
          </div>
          <div className="text-sm font-bold font-mono text-emerald-400 tracking-wider">
            {route.length > 0 ? route.join(' ➔ ') : 'Node 12 ➔ 13 ➔ 14 ➔ 19'}
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5 text-amber-400" /> ETA:</span>
            <span className="text-amber-300 font-bold">{decision?.estimated_time_minutes || 6} min</span>
          </div>
        </div>
      </div>

      {/* Signal Actions Stream */}
      {decision?.signal_actions && (
        <div className="pt-2 border-t border-slate-800">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
            Active Preemption Signals ({decision.signal_actions.length})
          </span>
          <div className="flex flex-wrap gap-2">
            {decision.signal_actions.map((sa: any, idx: number) => (
              <div key={idx} className="px-2.5 py-1 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs font-mono flex items-center gap-1.5">
                <CheckCircle className="w-3 h-3 text-emerald-400" />
                <span>Node {sa.node}</span>
                <span className="text-slate-400">({sa.axis})</span>
                <span className="font-bold text-white">🟢 PRIORITY</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
