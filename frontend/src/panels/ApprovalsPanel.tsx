import React from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Check, X, ShieldAlert } from 'lucide-react';

export const ApprovalsPanel: React.FC = () => {
  const { approvals, fetchApprovals } = useAppStore();

  const handleDecision = async (id: string, decision: 'approved' | 'rejected') => {
    try {
      await apiClient.decideApproval(id, decision);
      await fetchApprovals();
    } catch (e) {
      console.error('Failed to decide approval', e);
    }
  };

  return (
    <div className="p-3 flex flex-col space-y-3 h-[calc(100vh-140px)] overflow-y-auto text-xs">
      <div className="text-xs font-semibold text-slate-300 pb-2 border-b border-slate-800 flex items-center gap-1.5">
        <ShieldAlert size={14} className="text-amber-400" />
        Executive Approval Gates
      </div>

      {approvals.length === 0 ? (
        <div className="p-8 text-center text-slate-500 font-mono">
          No approval requests pending. The engine will pause and notify you here when critical gates trigger.
        </div>
      ) : (
        approvals.map((appr) => (
          <div key={appr.id} className="p-3 rounded-lg border border-slate-800 bg-slate-900/90 flex flex-col space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 capitalize">{appr.kind.replace('_', ' ')}</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase ${
                  appr.status === 'pending'
                    ? 'bg-amber-950 text-amber-400 border border-amber-800'
                    : appr.status === 'approved'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : 'bg-rose-950 text-rose-400 border border-rose-800'
                }`}
              >
                {appr.status}
              </span>
            </div>

            <pre className="text-[11px] bg-slate-950 p-2 rounded text-slate-300 font-mono overflow-x-auto">
              {JSON.stringify(appr.request_json, null, 2)}
            </pre>

            {appr.status === 'pending' && (
              <div className="flex gap-2 justify-end pt-1">
                <button
                  onClick={() => handleDecision(appr.id, 'rejected')}
                  className="px-3 py-1 rounded bg-rose-950/60 hover:bg-rose-900 border border-rose-800 text-rose-300 flex items-center gap-1 text-xs"
                >
                  <X size={13} /> Reject
                </button>
                <button
                  onClick={() => handleDecision(appr.id, 'approved')}
                  className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1 text-xs font-medium"
                >
                  <Check size={13} /> Approve
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
};
