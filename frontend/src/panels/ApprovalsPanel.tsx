import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Check, X, ShieldAlert, RefreshCw } from 'lucide-react';

export const ApprovalsPanel: React.FC = () => {
  const { approvals, fetchApprovals, networkStatus } = useAppStore();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDecision = async (id: string, decision: 'approved' | 'rejected') => {
    if (networkStatus === 'offline') return;
    setBusyId(id);
    setError(null);
    try {
      await apiClient.decideApproval(id, decision);
      await fetchApprovals();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save this decision.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="approvals-panel app-panel">
      <header className="approvals-header">
        <div>
          <h2><ShieldAlert size={16} /> Approvals</h2>
          <p>Decisions that need your review</p>
        </div>
        <button type="button" className="app-icon-button" onClick={() => void fetchApprovals()} disabled={networkStatus === 'offline'} aria-label="Refresh approvals">
          <RefreshCw size={14} />
        </button>
      </header>
      {networkStatus === 'offline' && <p className="app-inline-note" role="status">Offline. Showing the last approval snapshot.</p>}
      {error && <div className="app-error" role="alert">{error}</div>}
      <div className="approvals-list">
        {approvals.length === 0 ? (
          <div className="app-empty">
            <Check size={22} />
            <strong>No pending approvals</strong>
            <p>When a task reaches a decision gate, it will appear here.</p>
          </div>
        ) : approvals.map((approval) => (
          <article key={approval.id} className="approval-record">
            <div className="approval-record-heading">
              <strong>{approval.kind.replaceAll('_', ' ')}</strong>
              <span className={'approval-status approval-status-' + approval.status}>{approval.status}</span>
            </div>
            <pre>{JSON.stringify(approval.request_json, null, 2)}</pre>
            {approval.status === 'pending' && (
              <div className="approval-actions">
                <button type="button" className="app-button" disabled={busyId === approval.id || networkStatus === 'offline'} onClick={() => void handleDecision(approval.id, 'rejected')}>
                  <X size={13} /> Reject
                </button>
                <button type="button" className="app-button app-button-primary" disabled={busyId === approval.id || networkStatus === 'offline'} onClick={() => void handleDecision(approval.id, 'approved')}>
                  <Check size={13} /> Approve
                </button>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
};
