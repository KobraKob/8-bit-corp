import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Check, X, ShieldAlert, RefreshCw, Clock3 } from 'lucide-react';

export const ApprovalsPanel: React.FC = () => {
  const { approvals, approvalsLoading, approvalsError, fetchApprovals, networkStatus } = useAppStore();
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

  const pendingCount = approvals.filter((approval) => approval.status === 'pending').length;

  return (
    <section className="approvals-panel app-panel">
      <header className="approvals-header">
        <div>
          <h2><ShieldAlert size={16} /> Approvals</h2>
          <p>Decisions waiting for human review</p>
        </div>
        <button type="button" className="app-icon-button" onClick={() => void fetchApprovals()} disabled={networkStatus === 'offline'} aria-label="Refresh approvals">
          <RefreshCw size={14} />
        </button>
      </header>

      {approvalsError && (
        <div className="task-stale-notice" role="alert">
          {approvals.length ? 'Showing the last approval snapshot. ' : ''}
          {approvalsError}
        </div>
      )}
      {error && <div className="app-error" role="alert">{error}</div>}
      {networkStatus === 'offline' && <p className="app-inline-note">Offline. Approval decisions require a server connection.</p>}

      {approvalsLoading && approvals.length === 0 ? (
        <div className="task-tree-skeleton" aria-label="Loading approvals">
          {[0, 1].map((item) => <div className="task-tree-skeleton-item" key={item}><div className="app-skeleton app-skeleton-line" /><div className="app-skeleton app-skeleton-wide" /></div>)}
        </div>
      ) : approvals.length === 0 ? (
        <div className="app-empty">
          <Check size={22} />
          <strong>No approval requests</strong>
          <p>When an agent reaches an approval gate, the request will appear here.</p>
        </div>
      ) : (
        <div className="approvals-list">
          <div className="approvals-summary"><span>{pendingCount} awaiting decision</span><span>{approvals.length} total</span></div>
          {approvals.map((approval) => (
            <article key={approval.id} className="approval-record">
              <header className="approval-record-heading">
                <div>
                  <strong>{approval.kind.replaceAll('_', ' ')}</strong>
                  <span>{approval.project_id}{approval.task_id ? ' · ' + approval.task_id : ''}</span>
                </div>
                <span className={'approval-status approval-status-' + approval.status}>{approval.status}</span>
              </header>
              <pre>{JSON.stringify(approval.request_json, null, 2)}</pre>
              {approval.decided_at && <p className="approval-decided"><Clock3 size={11} /> Decided {new Date(approval.decided_at).toLocaleString()}</p>}
              {approval.status === 'pending' && (
                <div className="approval-actions">
                  <button type="button" className="app-button" disabled={busyId === approval.id || networkStatus === 'offline'} onClick={() => void handleDecision(approval.id, 'rejected')}>
                    <X size={13} /> Reject
                  </button>
                  <button type="button" className="app-button app-button-primary" disabled={busyId === approval.id || networkStatus === 'offline'} onClick={() => void handleDecision(approval.id, 'approved')}>
                    <Check size={13} /> {busyId === approval.id ? 'Saving' : 'Approve'}
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
};
