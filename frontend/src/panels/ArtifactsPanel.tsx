import React, { useEffect, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Artifact } from '../api/types';
import { Download, FileCode, FileText, Image, Archive, ExternalLink } from 'lucide-react';

export const ArtifactsPanel: React.FC = () => {
  const { activeProjectId, selectedArtifact, setSelectedArtifact } = useAppStore();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeContent, setActiveContent] = useState<string>('');

  useEffect(() => {
    // When selectedArtifact changes, load full content
    if (selectedArtifact) {
      apiClient.getArtifact(selectedArtifact.id).then((art) => {
        setActiveContent(art.content || art.summary);
      });
    }
  }, [selectedArtifact?.id]);

  if (!activeProjectId) {
    return <div className="p-6 text-center text-slate-500 text-xs">Select a project to inspect deliverables.</div>;
  }

  const exportUrl = apiClient.getProjectExportUrl(activeProjectId);

  return (
    <div className="p-3 flex flex-col space-y-3 h-[calc(100vh-140px)]">
      {/* Top action bar */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <span className="text-xs font-semibold text-slate-300">Project Deliverables</span>
        <a
          href={exportUrl}
          download
          className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-all"
        >
          <Archive size={13} className="text-amber-400" /> Export All (.zip)
        </a>
      </div>

      {selectedArtifact ? (
        <div className="flex-1 flex flex-col space-y-2 overflow-hidden">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-200">{selectedArtifact.path}</span>
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-slate-800 font-mono text-[10px] text-sky-400">
                {selectedArtifact.kind}
              </span>
              <a
                href={apiClient.getArtifactDownloadUrl(selectedArtifact.id)}
                download
                className="text-slate-400 hover:text-white"
              >
                <Download size={14} />
              </a>
            </div>
          </div>

          {/* Render preview */}
          <div className="flex-1 bg-slate-950 border border-slate-800 rounded p-3 overflow-y-auto font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
            {selectedArtifact.kind === 'image_svg' ? (
              <div
                className="bg-white/5 p-4 rounded flex justify-center items-center"
                dangerouslySetInnerHTML={{ __html: activeContent }}
              />
            ) : (
              activeContent
            )}
          </div>

          <button
            onClick={() => setSelectedArtifact(null)}
            className="text-xs text-slate-400 hover:underline pt-1 text-left"
          >
            ← Back to all artifacts
          </button>
        </div>
      ) : (
        <div className="flex flex-col space-y-2 overflow-y-auto">
          {artifacts.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs font-mono">
              Deliverables and artifacts created by agents will appear here as tasks finish.
            </div>
          ) : (
            artifacts.map((art) => (
              <div
                key={art.id}
                onClick={() => setSelectedArtifact(art)}
                className="p-2.5 rounded border border-slate-800 bg-slate-900/60 hover:border-slate-700 cursor-pointer flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2">
                  {art.kind === 'image_svg' ? (
                    <Image size={15} className="text-pink-400" />
                  ) : art.kind === 'code' ? (
                    <FileCode size={15} className="text-emerald-400" />
                  ) : (
                    <FileText size={15} className="text-sky-400" />
                  )}
                  <span className="text-slate-200 font-mono text-[11px]">{art.path}</span>
                </div>
                <span className="text-[10px] text-slate-500">v{art.version}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
