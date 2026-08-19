import React from 'react';
import { ShieldAlert, Cross, Navigation, Radio } from 'lucide-react';

interface LiveMapProps {
  telemetry: any;
  activeRoute: string[];
}

export const LiveMap: React.FC<LiveMapProps> = ({ telemetry, activeRoute }) => {
  const junctions = telemetry?.junctions || {};
  const ambulance = telemetry?.ambulance || {};
  const incidents = telemetry?.incidents || {};

  // Junction coordinate mapping in SVG canvas (400x400 viewBox)
  const coords: Record<string, { x: number; y: number }> = {
    J1: { x: 100, y: 100 },
    J2: { x: 300, y: 100 },
    J3: { x: 100, y: 300 },
    J4: { x: 300, y: 300 }
  };

  // Convert Webots position (-100..100) to SVG map space (100..300)
  const mapX = (x: number) => 100 + ((x + 100) / 200) * 200;
  const mapY = (y: number) => 100 + ((y + 100) / 200) * 200;

  const ambX = mapX(ambulance?.position?.x || -100);
  const ambY = mapY(ambulance?.position?.y || -100);

  const isRouteA = activeRoute.join('->') === 'J1->J2->J4';
  const isRouteB = activeRoute.join('->') === 'J1->J3->J4';

  const hasRouteAIncident = !!incidents['R_J1_J2'];
  const hasRouteBIncident = !!incidents['R_J1_J3'];

  return (
    <div className="relative w-full h-[460px] bg-slate-900/90 rounded-2xl border border-slate-800 p-4 overflow-hidden shadow-2xl">
      <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
        <span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-semibold uppercase tracking-wider">
          <Radio className="w-3.5 h-3.5 animate-pulse text-cyan-400" />
          Field Sensor Telemetry (4 Junction Grid)
        </span>
      </div>

      <svg className="w-full h-full" viewBox="0 0 400 400">
        {/* Grid Background */}
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
          </pattern>
          <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        <rect width="400" height="400" fill="url(#grid)" />

        {/* Roads Base */}
        {/* R_J1_J2 */}
        <line x1="100" y1="100" x2="300" y2="100" stroke="#334155" strokeWidth="14" strokeLinecap="round" />
        {/* R_J2_J4 */}
        <line x1="300" y1="100" x2="300" y2="300" stroke="#334155" strokeWidth="14" strokeLinecap="round" />
        {/* R_J1_J3 */}
        <line x1="100" y1="100" x2="100" y2="300" stroke="#334155" strokeWidth="14" strokeLinecap="round" />
        {/* R_J3_J4 */}
        <line x1="100" y1="300" x2="300" y2="300" stroke="#334155" strokeWidth="14" strokeLinecap="round" />

        {/* Active Dynamic Route Corridor Overlay */}
        {isRouteA && (
          <g filter="url(#glow-cyan)">
            <polyline points="100,100 300,100 300,300" fill="none" stroke="#06b6d4" strokeWidth="6" strokeDasharray="8 4" className="animate-pulse" />
          </g>
        )}
        {isRouteB && (
          <g filter="url(#glow-cyan)">
            <polyline points="100,100 100,300 300,300" fill="none" stroke="#10b981" strokeWidth="6" strokeDasharray="8 4" className="animate-pulse" />
          </g>
        )}

        {/* Incidents Warning Overlays */}
        {hasRouteAIncident && (
          <g transform="translate(200, 100)">
            <circle r="16" fill="rgba(244, 63, 94, 0.25)" className="animate-ping" />
            <circle r="12" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
            <text x="0" y="4" textAnchor="middle" fill="#ffffff" fontSize="10" fontWeight="bold">!</text>
          </g>
        )}
        {hasRouteBIncident && (
          <g transform="translate(100, 200)">
            <circle r="16" fill="rgba(244, 63, 94, 0.25)" className="animate-ping" />
            <circle r="12" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
            <text x="0" y="4" textAnchor="middle" fill="#ffffff" fontSize="10" fontWeight="bold">!</text>
          </g>
        )}

        {/* Junction Nodes J1-J4 */}
        {Object.entries(coords).map(([id, c]) => {
          const jState = junctions[id] || {};
          const isPriority = jState.priority_active;
          const isGreen = jState.signal_state?.includes('GREEN') || isPriority;
          const queue = jState.queue_length || 0;

          return (
            <g key={id} transform={`translate(${c.x}, ${c.y})`}>
              {/* Outer Glow Circle */}
              <circle
                r="22"
                fill={isPriority ? 'rgba(16, 185, 129, 0.2)' : 'rgba(30, 41, 59, 0.8)'}
                stroke={isPriority ? '#10b981' : (isGreen ? '#22c55e' : '#ef4444')}
                strokeWidth="3"
              />
              <text x="0" y="-28" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="600">
                {id}
              </text>

              {/* Signal Badge */}
              <circle r="6" fill={isGreen ? '#22c55e' : '#ef4444'} />

              {/* Queue Counter Badge */}
              <g transform="translate(16, -14)">
                <rect width="20" height="14" rx="4" fill="#0f172a" stroke="#475569" strokeWidth="1" />
                <text x="10" y="10" textAnchor="middle" fill="#f8fafc" fontSize="9" fontWeight="bold">
                  {queue}
                </text>
              </g>
            </g>
          );
        })}

        {/* Hospital Destination Icon at J4 */}
        <g transform="translate(330, 330)">
          <rect width="24" height="24" rx="6" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" />
          <text x="12" y="17" textAnchor="middle" fill="#ffffff" fontSize="14" fontWeight="bold">H</text>
        </g>

        {/* Ambulance Real Vehicle Position */}
        <g transform={`translate(${ambX}, ${ambY})`}>
          <circle r="18" fill="rgba(6, 182, 212, 0.3)" className="animate-ping" />
          <circle r="12" fill="#06b6d4" stroke="#ffffff" strokeWidth="2.5" />
          <path d="M-4,-4 L4,0 L-4,4 Z" fill="#ffffff" transform="rotate(45)" />
        </g>
      </svg>

      {/* Legend Bar */}
      <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between px-4 py-2 bg-slate-950/80 rounded-xl border border-slate-800 text-xs text-slate-400">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block" /> Route A Corridor</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" /> Route B Corridor</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" /> Incident / Block</span>
        </div>
        <div>
          Ambulance Pos: ({ambulance?.position?.x?.toFixed(0)}, {ambulance?.position?.y?.toFixed(0)})
        </div>
      </div>
    </div>
  );
};
