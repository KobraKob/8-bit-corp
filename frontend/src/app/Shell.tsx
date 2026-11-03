import React, { useEffect, useRef, useState } from 'react';
import Phaser from 'phaser';
import { OfficeScene } from '../office/OfficeScene';
import { LeftSidebar } from './LeftSidebar';
import { RightDrawer } from './RightDrawer';
import { BottomBar } from './BottomBar';
import { ProjectIntakeModal } from '../panels/ProjectIntakeModal';
import { LiveActivityHUD } from '../panels/LiveActivityHUD';
import { OfficeControlPanel } from '../panels/OfficeControlPanel';
import { useAppStore } from '../state/useAppStore';
import { wsClient } from '../state/wsClient';
import { PanelRight, X } from 'lucide-react';

export const Shell: React.FC = () => {
  const officeContainerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);

  const [isIntakeOpen, setIsIntakeOpen] = useState(false);
  const [isPanelsOpen, setIsPanelsOpen] = useState(false);
  const { fetchProjects, fetchAgents, fetchApprovals, fetchUsage, agents } = useAppStore();

  useEffect(() => {
    // Initial fetch of application state
    fetchProjects();
    fetchAgents();
    fetchApprovals();
    fetchUsage();

    // Connect WebSocket
    wsClient.connect();

    // Background sync loop every 2.5 seconds to guarantee the frontend stays live
    const interval = setInterval(() => {
      const activeId = useAppStore.getState().activeProjectId;
      if (activeId) {
        useAppStore.getState().fetchTaskTree();
      }
      useAppStore.getState().fetchProjects();
      useAppStore.getState().fetchUsage();
      useAppStore.getState().fetchApprovals();
    }, 2500);

    return () => {
      clearInterval(interval);
      wsClient.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!officeContainerRef.current || gameRef.current || agents.length === 0) return;

    // Initialize Phaser 3 Pixel Office Game
    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      parent: officeContainerRef.current,
      width: officeContainerRef.current.clientWidth || 800,
      height: officeContainerRef.current.clientHeight || 600,
      pixelArt: true,
      backgroundColor: '#090d16',
      scene: [OfficeScene],
      scale: {
        mode: Phaser.Scale.RESIZE,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
      render: {
        pixelArt: true,
        antialias: false,
        roundPixels: true,
      },
    };

    gameRef.current = new Phaser.Game(config);

    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, [agents.length]);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100">
      {/* Main 3-column Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        <div className="hidden shrink-0 lg:flex"><LeftSidebar onOpenIntake={() => setIsIntakeOpen(true)} /></div>

        {/* Center: Pixel Office Canvas with Live HUD */}
        <div className="relative min-w-0 flex-1 overflow-hidden bg-[#090d16]">
          {/* Top Live Progress & Status HUD */}
          <LiveActivityHUD />

          <OfficeControlPanel />

          {/* Phaser Canvas */}
          <div ref={officeContainerRef} className="w-full h-full" />

          <button onClick={() => setIsPanelsOpen(true)} className="absolute bottom-12 right-2 z-30 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-xs text-slate-200 shadow-xl 2xl:hidden">
            <PanelRight size={14} /> Control panels
          </button>
          {isPanelsOpen && <div className="absolute inset-y-0 right-0 z-40 w-[min(420px,94vw)] shadow-2xl 2xl:hidden">
            <button onClick={() => setIsPanelsOpen(false)} className="absolute right-3 top-3 z-50 rounded-md border border-slate-700 bg-slate-900 p-2 text-slate-200" aria-label="Close control panels"><X size={15} /></button>
            <RightDrawer />
          </div>}

          {/* Subtle controls overlay tooltip */}
          <div className="absolute bottom-2 left-2 bg-slate-950/80 backdrop-blur-sm border border-slate-800/80 px-2.5 py-1 rounded text-[10px] font-mono text-slate-400 pointer-events-none select-none z-10">
            Click employee or room • Right-drag to pan • Scroll to zoom
          </div>
        </div>

        {/* Right Drawer */}
        <div className="hidden shrink-0 2xl:flex"><RightDrawer /></div>
      </div>

      {/* Bottom Status / Payroll Bar */}
      <BottomBar />

      {/* Project Brief Intake Modal */}
      <ProjectIntakeModal isOpen={isIntakeOpen} onClose={() => setIsIntakeOpen(false)} />
    </div>
  );
};
