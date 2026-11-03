import React, { useEffect, useMemo, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Artifact } from '../api/types';
import { Download, FileCode, FileText, Image, Archive, RefreshCw } from 'lucide-react';

export const ArtifactsPanel: React.FC = () => {
  const { activeProjectId, selectedArtifact, setSelectedArtifact, events, networkStatus } = useAppStore();
  const [artifactCache, setArtifactCache] = useState<Record<string, Artifact[]>>({});
  const [contentCache, setContentCache] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingContent, setIsLoadingContent] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [contentError, setContentError] = useState<string | null>(null);
  const artifacts = activeProjectId ? artifactCache[activeProjectId] || [] : [];
  const activeContent = selectedArtifact ? contentCache[selectedArtifact.id] || '' : '';
  const latestArtifactEvent = useMemo(
    () => events.find((event) => event.type.startsWith('artifact.') && event.project_id === activeProjectId)?.id || 0,
    [events, activeProjectId]
  );

  useEffect(() => {
    if (selectedArtifact && selectedArtifact.project_id !== activeProjectId) setSelectedArtifact(null);
  }, [activeProjectId, selectedArtifact?.project_id, setSelectedArtifact]);

  const loadArtifacts = async () => {
    if (!activeProjectId || networkStatus === 'offline') return;
    setLoadError(null);
    setIsLoading((artifactCache[activeProjectId] || []).length === 0);
    try {
      const items = await apiClient.getArtifacts(activeProjectId);
      setArtifactCache((cache) => ({ ...cache, [activeProjectId]: items }));
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Could not load deliverables.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!activeProjectId) return;
    void loadArtifacts();
  }, [activeProjectId, latestArtifactEvent]);

  useEffect(() => {
    if (!selectedArtifact || contentCache[selectedArtifact.id]) return;
    let cancelled = false;
    setContentError(null);
    setIsLoadingContent(true);
    apiClient.getArtifact(selectedArtifact.id)
      .then((artifact) => {
        if (!cancelled) setContentCache((cache) => ({
          ...cache,
          [selectedArtifact.id]: artifact.content || artifact.summary || '',
        }));
      })
      .catch((error) => {
        if (!cancelled) setContentError(error instanceof Error ? error.message : 'Could not load this deliverable.');
      })
      .finally(() => { if (!cancelled) setIsLoadingContent(false); });
    return () => { cancelled = true; };
  }, [selectedArtifact?.id]);

  if (!activeProjectId) {
    return <div className="app-empty"><Archive size={22} /><strong>No project selected</strong><p>Select a project to inspect its deliverables.</p></div>;
  }

  return (
    <section className="artifacts-panel app-panel">
      <header className="artifacts-header">
        <div>
          <h2>Deliverables</h2>
          <p>{artifacts.length} saved files in this project</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="app-icon-button" onClick={() => void loadArtifacts()} disabled={isLoading || networkStatus === 'offline'} aria-label="Refresh deliverables">
            <RefreshCw size={14} />
          </button>
          <a href={apiClient.getProjectExportUrl(activeProjectId)} download className="app-button">
            <Archive size={13} /> Export ZIP
          </a>
        </div>
      </header>

      {loadError && (
        <div className="task-stale-notice" role="alert">
          {networkStatus === 'offline' ? 'Offline. ' : 'Could not refresh. '}
          {artifacts.length ? 'Showing the last saved deliverables.' : loadError}
          <button type="button" onClick={() => void loadArtifacts()} disabled={networkStatus === 'offline'}>Retry</button>
        </div>
      )}

      {selectedArtifact ? (
        <div className="artifact-detail">
          <header className="artifact-detail-header">
            <strong>{selectedArtifact.path}</strong>
            <div className="flex items-center gap-2">
              <span className="artifact-kind">{selectedArtifact.kind}</span>
              <a href={apiClient.getArtifactDownloadUrl(selectedArtifact.id)} download aria-label="Download deliverable"><Download size={14} /></a>
            </div>
          </header>
          <div className="artifact-content app-measured">
            {selectedArtifact.kind === 'image_svg' ? (
              <iframe title={selectedArtifact.path} sandbox="" srcDoc={activeContent || selectedArtifact.summary} />
            ) : isLoadingContent && !activeContent ? (
              <p className="app-muted">Loading deliverable content…</p>
            ) : contentError ? (
              <div className="app-error" role="alert">{contentError} {selectedArtifact.summary}</div>
            ) : (
              activeContent || selectedArtifact.summary || 'This deliverable has no text preview.'
            )}
          </div>
          <button type="button" className="artifact-back" onClick={() => setSelectedArtifact(null)}>Back to deliverables</button>
        </div>
      ) : isLoading && artifacts.length === 0 ? (
        <div className="task-tree-skeleton" aria-label="Loading deliverables">
          {[0, 1, 2].map((item) => <div className="task-tree-skeleton-item" key={item}><div className="app-skeleton app-skeleton-line" /><div className="app-skeleton app-skeleton-wide" /></div>)}
        </div>
      ) : artifacts.length === 0 ? (
        <div className="app-empty">
          <Archive size={22} />
          <strong>No deliverables yet</strong>
          <p>Files created by agents will appear here. The ZIP export becomes useful after the first file is saved.</p>
        </div>
      ) : (
        <div className="artifact-list">
          {artifacts.map((artifact) => (
            <button key={artifact.id} type="button" onClick={() => setSelectedArtifact(artifact)} className="artifact-row">
              <span className="artifact-row-icon">
                {artifact.kind === 'image_svg' ? <Image size={16} /> : artifact.kind === 'code' ? <FileCode size={16} /> : <FileText size={16} />}
              </span>
              <span className="artifact-row-copy">
                <strong>{artifact.path}</strong>
                <span>{artifact.kind}, version {artifact.version}</span>
              </span>
              <Download size={14} />
            </button>
          ))}
        </div>
      )}
    </section>
  );
};
