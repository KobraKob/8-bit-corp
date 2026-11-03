import React, { useEffect, useRef, useState } from 'react';
import Phaser from 'phaser';
import { Wifi, WifiOff, PanelRight, Plus, Radio } from 'lucide-react';
import { OfficeScene } from '../office/OfficeScene';
import { LeftSidebar } from './LeftSidebar';
import { RightDrawer } from './RightDrawer';
import { BottomBar } from './BottomBar';
import { ProjectIntakeModal } from '../panels/ProjectIntakeModal';
import { LiveActivityHUD } from '../panels/LiveActivityHUD';
import { useAppStore } from '../state/useAppStore';
import { wsClient } from '../state/wsClient';

export const Shell: React.FC = () => {
  const officeContainerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  const [isIntakeOpen, setIsIntakeOpen] = useState(false);
  const {
    fetchProjects, fetchApprovals, fetchUsage, fetchAgents, fetchKeys,
    isDrawerOpen, setDrawerOpen, networkStatus, projects, activeProjectId,
    setNetworkStatus,
  } = useAppStore();

  const activeProject = projects.find((project) => project.id === activeProjectId);

  useEffect(() => {
    const refreshAll = () => {
      if (!navigator.onLine) {
        setNetworkStatus('offline');
        return;
      }
      void fetchProjects();
      void fetchApprovals();
      void fetchUsage();
      void fetchAgents();
      void fetchKeys();
      void useAppStore.getState().fetchTaskTree();
    };

    refreshAll();
    wsClient.connect();

    const onOffline = () => {
      setNetworkStatus('offline');
      wsClient.disconnect();
    };
    const onOnline = () => {
      setNetworkStatus('online');
      wsClient.connect();
      refreshAll();
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') refreshAll();
    };

    window.addEventListener('offline', onOffline);
    window.addEventListener('online', onOnline);
    document.addEventListener('visibilitychange', onVisibility);

    // The office is a live workspace, but background polling stays bounded.
    const taskSync = window.setInterval(() => {
      if (navigator.onLine && document.visibilityState === 'visible') {
        void useAppStore.getState().fetchTaskTree();
      }
    }, 10000);
    const metadataSync = window.setInterval(() => {
      if (navigator.onLine && document.visibilityState === 'visible') {
        void useAppStore.getState().fetchProjects();
        void useAppStore.getState().fetchApprovals();
        void useAppStore.getState().fetchUsage();
      }
    }, 30000);

    return () => {
      window.clearInterval(taskSync);
      window.clearInterval(metadataSync);
      window.removeEventListener('offline', onOffline);
      window.removeEventListener('online', onOnline);
      document.removeEventListener('visibilitychange', onVisibility);
      wsClient.disconnect();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const initializeOffice = async () => {
      await fetchAgents();
      if (cancelled || !officeContainerRef.current || gameRef.current) return;

      const config: Phaser.Types.Core.GameConfig = {
        type: Phaser.AUTO,
        parent: officeContainerRef.current,
        width: officeContainerRef.current.clientWidth || 800,
        height: officeContainerRef.current.clientHeight || 600,
        pixelArt: true,
        backgroundColor: '#111a22',
        scene: [OfficeScene],
        scale: { mode: Phaser.Scale.RESIZE, autoCenter: Phaser.Scale.CENTER_BOTH },
        render: { pixelArt: true, antialias: false, roundPixels: true },
      };
      gameRef.current = new Phaser.Game(config);
    };

    void initializeOffice();
    return () => {
      cancelled = true;
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  const connectionLabel = networkStatus === 'connected'
    ? 'Live'
    : networkStatus === 'offline'
      ? 'Offline'
      : networkStatus === 'degraded'
        ? 'Reconnecting'
        : 'Online';

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div className="app-brand">
          <span className="app-brand-mark" aria-hidden="true">P</span>
          <div>
            <div className="app-brand-name">Pixel Corp</div>
            <div className="app-brand-caption">Virtual office</div>
          </div>
        </div>

        <div className="app-topbar-context">
          <span className="app-context-label">Current workspace</span>
          <span className="app-context-name">{activeProject?.name || 'No project selected'}</span>
        </div>

        <div className="app-topbar-actions">
          <span className={'app-connection app-connection-' + networkStatus} role="status" aria-live="polite">
            {networkStatus === 'offline' ? <WifiOff size={14} /> : networkStatus === 'connected' ? <Radio size={14} /> : <Wifi size={14} />}
            {connectionLabel}
          </span>
          <button type="button" className="app-button app-button-primary" onClick={() => setIsIntakeOpen(true)}>
            <Plus size={15} /> New project
          </button>
          <button
            type="button"
            className="app-icon-button"
            onClick={() => setDrawerOpen(!isDrawerOpen)}
            aria-label={isDrawerOpen ? 'Close workspace panel' : 'Open workspace panel'}
            aria-expanded={isDrawerOpen}
            title={isDrawerOpen ? 'Close workspace panel' : 'Open workspace panel'}
          >
            <PanelRight size={17} />
          </button>
        </div>
      </header>

      <div className="app-body">
        <LeftSidebar onOpenIntake={() => setIsIntakeOpen(true)} />
        <main className="app-office">
          <LiveActivityHUD />
          <div ref={officeContainerRef} className="app-office-canvas" />
          <div className="app-office-hint">
            Select an agent to inspect their work. Right-drag to pan. Scroll to zoom.
          </div>
        </main>
        {isDrawerOpen && <RightDrawer />}
      </div>

      <BottomBar />
      <ProjectIntakeModal isOpen={isIntakeOpen} onClose={() => setIsIntakeOpen(false)} />
    </div>
  );
};
