import React from 'react';
import { Terminal, ShieldCheck, Cpu, AlertTriangle } from 'lucide-react';

interface AlertAuditStreamProps {
  orchestration: any;
  incidents: Record<string, any>;
}

export const AlertAuditStream: React.FC<AlertAuditStreamProps> = ({ orchestration, incidents }) => {
  const reason = orchestration?.decision_reason || 'System Monitoring Nominal';
  const safetyPassed = orchestration?.safety_passed ?? true;
  const topStrats = orchestration?.what_if_top_3 || [];

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-cyan-400" />
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Multi-Agent Intelligence Stream</h2>
        </div>
        <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-400">
          <ShieldCheck className="w-3.5 h-3.5" /> Safety Approved
        </span>
      </div>

      {/* Latest Decision Banner */}
      <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800 space-y-1.5 font-mono text-xs">
        <div className="flex items-center justify-between text-slate-400">
          <span className="flex items-center gap-1.5 text-cyan-400 font-sans font-bold">
            <Cpu className="w-3.5 h-3.5" /> Orchestration Decision Reason:
          </span>
          <span className="text-[10px] text-slate-500">Live Agent Audit</span>
        </div>
        <div className="text-slate-200 font-semibold">{reason}</div>
      </div>

      {/* Top What-If Strategy Candidates */}
      {topStrats.length > 0 && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Top What-If Strategy Rankings:</span>
          <div className="grid grid-cols-3 gap-2">
            {topStrats.map((s: any, idx: number) => (
              <div
                key={idx}
                className={`p-2 rounded-lg text-[11px] border ${
                  idx === 0
                    ? 'bg-cyan-950/40 border-cyan-500/40 text-cyan-300 font-semibold'
                    : 'bg-slate-950/40 border-slate-800 text-slate-400'
                }`}
              >
                <div className="truncate">{s.strategy_name}</div>
                <div className="text-[10px] opacity-80">ETA: {s.simulated_eta_sec}s | Score: {s.composite_score}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
