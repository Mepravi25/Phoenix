import React from 'react';
import { Sliders, Flame, Trash2, ToggleLeft, ToggleRight, Layers } from 'lucide-react';

interface ControlPanelProps {
  mode: string;
  onToggleMode: (newMode: string) => void;
  onInjectIncident: (roadId: string) => void;
  onClearIncidents: () => void;
  onSetTrafficProfile: (profile: string) => void;
  hasIncidents: boolean;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  mode,
  onToggleMode,
  onInjectIncident,
  onClearIncidents,
  onSetTrafficProfile,
  hasIncidents
}) => {
  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sliders className="w-5 h-5 text-cyan-400" />
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Simulation Command Panel</h2>
        </div>
      </div>

      <div className="space-y-3">
        {/* BASELINE vs SWIFT Toggle */}
        <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800">
          <div>
            <div className="text-xs font-bold text-white">System Mode</div>
            <div className="text-[11px] text-slate-400">Switch between static cycles and SWIFT multi-agent</div>
          </div>
          <button
            onClick={() => onToggleMode(mode === 'SWIFT' ? 'BASELINE' : 'SWIFT')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              mode === 'SWIFT'
                ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {mode === 'SWIFT' ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
            {mode} MODE
          </button>
        </div>

        {/* Dynamic Incident Demo Button */}
        <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800">
          <div>
            <div className="text-xs font-bold text-rose-400 flex items-center gap-1.5">
              <Flame className="w-3.5 h-3.5 fill-rose-400" /> Dynamic Incident Scenario
            </div>
            <div className="text-[11px] text-slate-400">Simulate accident on Route A (R_J1_J2) mid-journey</div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onInjectIncident('R_J1_J2')}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-500/20 border border-rose-500/40 text-rose-300 hover:bg-rose-500/30 transition-all"
            >
              Inject Accident
            </button>
            {hasIncidents && (
              <button
                onClick={onClearIncidents}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition-all"
                title="Clear Incidents"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Traffic Density Selector */}
        <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800">
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-purple-400" /> Traffic Density Profile
            </div>
            <div className="text-[11px] text-slate-400">Low, Medium, or Heavy traffic load</div>
          </div>
          <div className="flex items-center gap-1">
            {['LOW', 'MEDIUM', 'HIGH'].map((prof) => (
              <button
                key={prof}
                onClick={() => onSetTrafficProfile(prof)}
                className="px-2.5 py-1 rounded text-[10px] font-bold bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all"
              >
                {prof}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
