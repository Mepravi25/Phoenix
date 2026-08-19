import React from 'react';
import { Cpu, ShieldCheck, Zap } from 'lucide-react';

interface SignalGridProps {
  junctions?: Record<string, any>;
  nodes25?: any[];
  decision?: any;
}

export const SignalGrid: React.FC<SignalGridProps> = ({ junctions = {}, nodes25 = [], decision }) => {
  // If 25-node telemetry is available, render 5x5 Grid (nodes 0..24)
  const routeNodes = decision?.route || [];
  const totalQueue = nodes25.reduce((sum, n) => sum + (n.queue_length || 0), 0);

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-emerald-400" />
          <div>
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
              25-Node Intersection Control Grid
            </h2>
            <p className="text-xs text-slate-500">5 × 5 Real Simulation Intersection Matrix</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-cyan-400 bg-cyan-500/10 px-2.5 py-1 rounded-full border border-cyan-500/20">
            Total Queue: {totalQueue} veh
          </span>
          <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
            <ShieldCheck className="w-3.5 h-3.5" /> 25 Nodes Active
          </div>
        </div>
      </div>

      {nodes25.length > 0 ? (
        <div className="grid grid-cols-5 gap-2 max-h-[380px] overflow-y-auto pr-1">
          {nodes25.map((node: any) => {
            const isPreempted = node.preemption_active;
            const isOnRoute = routeNodes.includes(node.node);
            const phase = node.light_phase || 'NS_GREEN';
            const isGreen = phase.includes('GREEN') || isPreempted;

            return (
              <div
                key={node.node}
                className={`p-2 rounded-xl border text-center transition-all ${
                  isPreempted
                    ? 'bg-emerald-950/70 border-emerald-400 shadow-md shadow-emerald-950/80 animate-pulse'
                    : isOnRoute
                    ? 'bg-cyan-950/50 border-cyan-500/50'
                    : 'bg-slate-900/60 border-slate-800'
                }`}
              >
                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
                  <span className="font-bold text-white">N{node.node}</span>
                  {isPreempted ? (
                    <span className="bg-emerald-500 text-slate-950 px-1 rounded font-bold">PRIORITY</span>
                  ) : isOnRoute ? (
                    <span className="bg-cyan-500/20 text-cyan-300 px-1 rounded font-semibold">ROUTE</span>
                  ) : (
                    <span className="text-slate-500">{node.active_direction}</span>
                  )}
                </div>

                <div className="text-[11px] font-bold tracking-tight">
                  <span className={isPreempted ? 'text-emerald-300' : isGreen ? 'text-emerald-400' : 'text-amber-400'}>
                    {isPreempted ? '🟢 PRIORITY' : phase}
                  </span>
                </div>

                <div className="mt-1.5 pt-1 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono">
                  <span className="text-slate-400">Queue:</span>
                  <span className={`font-bold ${node.queue_length > 10 ? 'text-rose-400' : node.queue_length > 5 ? 'text-amber-300' : 'text-slate-300'}`}>
                    {node.queue_length}
                  </span>
                </div>

                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-slate-400">Flush:</span>
                  <span className="text-slate-300">{node.flush_time}s</span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Fallback 4-Junction baseline cards */
        <div className="grid grid-cols-2 gap-3">
          {['J1', 'J2', 'J3', 'J4'].map((id) => {
            const j = junctions[id] || {};
            const isPriority = j.priority_active;
            return (
              <div key={id} className={`p-3 rounded-xl border ${isPriority ? 'bg-emerald-950/40 border-emerald-500/50' : 'bg-slate-950/50 border-slate-800'}`}>
                <div className="flex items-center justify-between mb-1 text-xs">
                  <span className="font-bold text-white">{id}</span>
                  <span className="text-emerald-400 font-semibold">{j.signal_state || 'GREEN_NS'}</span>
                </div>
                <div className="text-xs text-slate-400">Queue: {j.queue_length || 0} vehicles</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
