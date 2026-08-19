import React from 'react';
import { Navigation, Clock, Activity, AlertTriangle } from 'lucide-react';

interface RouteEtaCardProps {
  ambulance: any;
  activeRoute: string[];
  mode: string;
}

export const RouteEtaCard: React.FC<RouteEtaCardProps> = ({ ambulance, activeRoute, mode }) => {
  const routeString = activeRoute && activeRoute.length > 0 ? activeRoute.join(' → ') + ' → Hospital' : 'Calculating...';
  const eta = ambulance?.eta_seconds ?? 0;
  const speed = ambulance?.speed ?? 0;
  const dist = (ambulance?.remaining_distance_m ?? 0) / 1000;
  const stopped = ambulance?.stopped_in_traffic;

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Navigation className="w-5 h-5 text-cyan-400" />
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Active Route & Telemetry</h2>
        </div>
        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${mode === 'SWIFT' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'bg-slate-800 text-slate-400'}`}>
          {mode} MODE
        </span>
      </div>

      <div className="p-3.5 bg-slate-950/70 rounded-xl border border-slate-800">
        <span className="text-xs text-slate-500 font-medium">Selected Route Path:</span>
        <div className="text-base font-bold text-cyan-300 mt-0.5 tracking-wide">
          {routeString}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Clock className="w-3.5 h-3.5 text-cyan-400" /> ETA
          </div>
          <div className="text-xl font-extrabold text-white mt-1">
            {eta > 0 ? `${eta.toFixed(1)}s` : (ambulance?.has_arrived ? 'ARRIVED' : '0s')}
          </div>
        </div>

        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Activity className="w-3.5 h-3.5 text-emerald-400" /> Speed
          </div>
          <div className="text-xl font-extrabold text-white mt-1">
            {speed.toFixed(0)} <span className="text-xs font-normal text-slate-400">km/h</span>
          </div>
        </div>

        <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Navigation className="w-3.5 h-3.5 text-purple-400" /> Remaining
          </div>
          <div className="text-xl font-extrabold text-white mt-1">
            {dist.toFixed(2)} <span className="text-xs font-normal text-slate-400">km</span>
          </div>
        </div>
      </div>

      {stopped && (
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Ambulance delayed in normal traffic queue (Waiting count: {ambulance?.stops_count || 1})</span>
        </div>
      )}
    </div>
  );
};
