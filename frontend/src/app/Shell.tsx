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

export const Shell: React.FC = () => {
  const officeContainerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);

  const [isIntakeOpen, setIsIntakeOpen] = useState(false);
  const { fetchProjects, fetchAgents, fetchApprovals, fetchUsage } = useAppStore();

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
    if (!officeContainerRef.current || gameRef.current) return;

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
  }, []);

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
