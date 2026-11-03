import React, { useEffect, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Artifact } from '../api/types';
import { Download, FileCode, FileText, Image, Archive } from 'lucide-react';

export const ArtifactsPanel: React.FC = () => {
  const { activeProjectId, selectedArtifact, setSelectedArtifact, events } = useAppStore();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeContent, setActiveContent] = useState('');

  useEffect(() => {
    if (selectedArtifact && selectedArtifact.project_id !== activeProjectId) {
      setSelectedArtifact(null);
    }
  }, [activeProjectId, selectedArtifact?.project_id, setSelectedArtifact]);

  useEffect(() => {
    if (!activeProjectId) {
      setArtifacts([]);
      return;
    }
    let cancelled = false;
    apiClient.getArtifacts(activeProjectId)
      .then((items) => { if (!cancelled) setArtifacts(items); })
      .catch((error) => console.error('Failed to load project artifacts', error));
    return () => { cancelled = true; };
  }, [activeProjectId, events[0]?.id]);

  useEffect(() => {
    if (!selectedArtifact) {
      setActiveContent('');
      return;
    }
    let cancelled = false;
    setActiveContent('');
    apiClient.getArtifact(selectedArtifact.id)
      .then((artifact) => { if (!cancelled) setActiveContent(artifact.content || artifact.summary); })
      .catch((error) => console.error('Failed to load artifact content', error));
    return () => { cancelled = true; };
  }, [selectedArtifact?.id]);

  if (!activeProjectId) {
    return <div className="p-6 text-center text-slate-500 text-xs">Select a project to inspect deliverables.</div>;
  }

  return (
    <div className="p-3 flex flex-col space-y-3 h-[calc(100vh-140px)]">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <span className="text-xs font-semibold text-slate-300">Project Deliverables ({artifacts.length})</span>
        <a href={apiClient.getProjectExportUrl(activeProjectId)} download className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-all">
          <Archive size={13} className="text-amber-400" /> Export All (.zip)
        </a>
      </div>
      {selectedArtifact ? (
        <div className="flex-1 flex flex-col space-y-2 overflow-hidden">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-200 truncate">{selectedArtifact.path}</span>
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-slate-800 font-mono text-[10px] text-sky-400">{selectedArtifact.kind}</span>
              <a href={apiClient.getArtifactDownloadUrl(selectedArtifact.id)} download className="text-slate-400 hover:text-white" aria-label="Download artifact"><Download size={14} /></a>
            </div>
          </div>
          <div className="flex-1 bg-slate-950 border border-slate-800 rounded p-3 overflow-y-auto font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
            {selectedArtifact.kind === 'image_svg'
              ? <iframe title={selectedArtifact.path} sandbox="" srcDoc={activeContent} className="w-full min-h-64 h-full bg-slate-900 rounded" />
              : activeContent || 'Loading artifact…'}
          </div>
          <button onClick={() => setSelectedArtifact(null)} className="text-xs text-slate-400 hover:underline pt-1 text-left">← Back to all artifacts</button>
        </div>
      ) : (
        <div className="flex flex-col space-y-2 overflow-y-auto">
          {artifacts.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs font-mono">Deliverables created by agents will appear here after submission.</div>
          ) : artifacts.map((artifact) => (
            <button key={artifact.id} type="button" onClick={() => setSelectedArtifact(artifact)} className="p-2.5 rounded border border-slate-800 bg-slate-900/60 hover:border-sky-700 cursor-pointer flex items-center justify-between text-xs text-left">
              <span className="flex items-center gap-2 min-w-0">
                {artifact.kind === 'image_svg' ? <Image size={15} className="text-pink-400 shrink-0" /> : artifact.kind === 'code' ? <FileCode size={15} className="text-emerald-400 shrink-0" /> : <FileText size={15} className="text-sky-400 shrink-0" />}
                <span className="text-slate-200 font-mono text-[11px] truncate">{artifact.path}</span>
              </span>
              <span className="text-[10px] text-slate-500 shrink-0">v{artifact.version}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
