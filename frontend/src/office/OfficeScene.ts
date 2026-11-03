import Phaser from 'phaser';
import EasyStar from 'easystarjs';
import { Agent } from '../api/types';
import { generateBuildingLayout } from './buildingLayout';
import { proceduralPixelArt } from './proceduralArt';
import { AgentActionState, BuildingLayout, DeskPosition } from './types';
import { useAppStore } from '../state/useAppStore';

interface AgentSprite {
  agent: Agent;
  container: Phaser.GameObjects.Container;
  sprite: Phaser.GameObjects.Sprite;
  state: AgentActionState;
  desk?: DeskPosition;
  bubbleContainer?: Phaser.GameObjects.Container;
  currentPath?: Array<{ x: number; y: number }>;
}

export class OfficeScene extends Phaser.Scene {
  private layout!: BuildingLayout;
  private pathfinder = new EasyStar.js();
  private agentSprites: Map<string, AgentSprite> = new Map();
  private isPanning = false;
  private panStartX = 0;
  private panStartY = 0;
  private lastHandledEventIndex = 0;

  constructor() {
    super({ key: 'OfficeScene' });
  }

  preload() {
    // Generate procedural pixel-art textures
    proceduralPixelArt.generateTextures(this);
  }

  create() {
    const agents = useAppStore.getState().agents.filter((agent) => agent.status === 'active');
    this.lastHandledEventIndex = Math.max(0, ...useAppStore.getState().events.map((event) => event.id));
    this.layout = generateBuildingLayout(agents);

    // Setup EasyStar Pathfinding
    this.pathfinder.setGrid(this.layout.collisionMatrix);
    this.pathfinder.setAcceptableTiles([0]);
    this.pathfinder.enableDiagonals();
    this.pathfinder.disableCornerCutting();

    // Draw Office Architecture
    this.drawBuilding();

    // Spawn Agents at their assigned desks
    this.spawnAgents(agents);

    // Camera Configuration & Controls
    const cam = this.cameras.main;
    cam.setBounds(0, 0, this.layout.gridWidth * 16, this.layout.gridHeight * 16);
    cam.setZoom(1.8);
    // Center camera on Executive / Engineering floor initially
    cam.centerOn(36 * 16, 20 * 16);

    this.setupCameraControls();

    // Subscribe to state events
    const unsubscribe = useAppStore.subscribe((state) => {
      this.syncAgents(state.agents);
      this.processNewEvents(state.events);
    });
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, unsubscribe);
  }

  private drawBuilding() {
    const ts = 16;
    const graphics = this.add.graphics();

    // Draw base building floor
    for (let x = 0; x < this.layout.gridWidth; x++) {
      for (let y = 0; y < this.layout.gridHeight; y++) {
        const isDark = (x + y) % 2 === 0;
        this.add.image(x * ts + ts / 2, y * ts + ts / 2, isDark ? 'tile_floor_dark' : 'tile_floor_light');
      }
    }

    // Draw Room Floors & Walls
    for (const room of this.layout.rooms) {
      // Floor tint
      graphics.fillStyle(room.floorColor, 0.4);
      graphics.fillRect(
        room.bounds.x * ts,
        room.bounds.y * ts,
        room.bounds.width * ts,
        room.bounds.height * ts
      );

      // Room Title Sign
      this.add
        .text(room.bounds.x * ts + 8, room.bounds.y * ts + 4, room.name.toUpperCase(), {
          fontSize: '9px',
          fontFamily: 'monospace',
          color: '#ffffff',
          backgroundColor: '#0f172a',
          padding: { x: 3, y: 1 },
        })
        .setDepth(2);

      // Walls
      for (let x = room.bounds.x; x < room.bounds.x + room.bounds.width; x++) {
        for (let y = room.bounds.y; y < room.bounds.y + room.bounds.height; y++) {
          if (this.layout.collisionMatrix[y][x] === 1) {
            this.add.image(x * ts + ts / 2, y * ts + ts / 2, 'tile_wall').setDepth(1);
          }
        }
      }

      // Desks & Office Equipment
      for (const desk of room.desks) {
        // Desk image
        this.add.image(desk.tileX * ts + ts / 2, desk.tileY * ts + ts / 2, 'furniture_desk').setDepth(2);
        // Computer Monitor
        this.add.image(desk.tileX * ts + ts / 2, desk.tileY * ts + ts / 2 - 2, 'furniture_computer').setDepth(3);
        // Office Chair
        this.add.image(desk.tileX * ts + ts / 2, desk.tileY * ts + ts / 2 + 8, 'furniture_chair').setDepth(1);
      }
    }

    // Decorate Lobby & Breakroom
    this.add.image(this.layout.lobbyDesk.tileX * ts, this.layout.lobbyDesk.tileY * ts, 'furniture_desk').setDepth(2);
    this.add.text(this.layout.lobbyDesk.tileX * ts - 16, this.layout.lobbyDesk.tileY * ts - 14, 'INTAKE DESK', {
      fontSize: '8px',
      color: '#38bdf8',
      fontFamily: 'monospace',
      backgroundColor: '#0f172a',
    });

    this.add.image(this.layout.breakRoom.tileX * ts, this.layout.breakRoom.tileY * ts, 'furniture_watercooler').setDepth(2);
    this.add.image(this.layout.breakRoom.tileX * ts + 16, this.layout.breakRoom.tileY * ts, 'furniture_plant').setDepth(2);
  }

  private spawnAgents(agents: Agent[]) {
    const ts = 16;
    for (const agent of agents) {
      // Find assigned desk
      let desk: DeskPosition | undefined;
      for (const r of this.layout.rooms) {
        desk = r.desks.find((d) => d.agentId === agent.id);
        if (desk) break;
      }

      const spawnX = desk ? desk.tileX * ts + ts / 2 : this.layout.lobbyDesk.tileX * ts;
      const spawnY = desk ? desk.tileY * ts + ts / 2 + 6 : this.layout.lobbyDesk.tileY * ts;

      // Create procedural texture key for this agent
      const shirt = agent.sprite_json?.shirt_color || '#3b82f6';
      const isCeo = agent.role_key === 'ceo';
      const textureKey = proceduralPixelArt.createCustomAgentTexture(
        this,
        `agent_tex_${agent.id}`,
        shirt,
        agent.sprite_json?.skin_tone || 2,
        agent.level,
        isCeo
      );

      const container = this.add.container(spawnX, spawnY).setDepth(10);
      const sprite = this.add.sprite(0, 0, textureKey);
      sprite.setInteractive({ cursor: 'pointer' });

      // Name tag over agent
      const nameTag = this.add
        .text(0, -12, agent.display_name.split(' ')[0], {
          fontSize: '7px',
          fontFamily: 'monospace',
          color: '#ffffff',
          backgroundColor: '#0f172a',
          padding: { x: 2, y: 1 },
        })
        .setOrigin(0.5);

      container.add([sprite, nameTag]);

      // Click to inspect agent
      sprite.on('pointerdown', () => {
        useAppStore.getState().setSelectedAgent(agent.id);
      });

      this.agentSprites.set(agent.id, {
        agent,
        container,
        sprite,
        state: 'working',
        desk,
      });
    }
  }

  private syncAgents(agents: Agent[]) {
    const activeIds = new Set(agents.filter((agent) => agent.status === 'active').map((agent) => agent.id));

    // Remove retired/deleted agents instead of leaving stale sprites in the office.
    for (const [agentId, entry] of this.agentSprites) {
      if (!activeIds.has(agentId)) {
        entry.bubbleContainer?.destroy();
        entry.container.destroy(true);
        this.agentSprites.delete(agentId);
      }
    }

    for (const agent of agents) {
      if (agent.status === 'active' && !this.agentSprites.has(agent.id)) {
        this.spawnAgents([agent]);
      }
    }
  }

  private setupCameraControls() {
    this.input.on('pointerdown', (pointer: Phaser.Input.Pointer, currentlyOver: Phaser.GameObjects.GameObject[] = []) => {
      // Preserve left-click selection on agents; allow left-drag on empty floor and right/middle drag.
      if (pointer.leftButtonDown() && currentlyOver.length > 0) return;
      if (pointer.rightButtonDown() || pointer.middleButtonDown() || pointer.leftButtonDown()) {
        this.isPanning = true;
        this.panStartX = pointer.x;
        this.panStartY = pointer.y;
      }
    });

    this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (this.isPanning) {
        const dx = (this.panStartX - pointer.x) / this.cameras.main.zoom;
        const dy = (this.panStartY - pointer.y) / this.cameras.main.zoom;
        this.cameras.main.scrollX += dx;
        this.cameras.main.scrollY += dy;
        this.panStartX = pointer.x;
        this.panStartY = pointer.y;
      }
    });

    this.input.on('pointerup', () => {
      this.isPanning = false;
    });

    // Zoom on wheel
    this.input.on('wheel', (pointer: Phaser.Input.Pointer, gameObjects: any, deltaX: number, deltaY: number) => {
      const newZoom = Phaser.Math.Clamp(this.cameras.main.zoom - deltaY * 0.001, 1.0, 3.5);
      this.cameras.main.setZoom(newZoom);
    });
  }

  private showAgentBubble(agentId: string, texture: 'bubble_thinking' | 'bubble_blocked', durationMs = 3000) {
    const entry = this.agentSprites.get(agentId);
    if (!entry) return;

    if (entry.bubbleContainer) {
      entry.bubbleContainer.destroy();
    }

    const bubble = this.add.image(0, -22, texture).setOrigin(0.5);
    const bubbleContainer = this.add.container(0, 0, [bubble]);
    entry.container.add(bubbleContainer);
    entry.bubbleContainer = bubbleContainer;

    this.time.delayedCall(durationMs, () => {
      if (entry.bubbleContainer === bubbleContainer) {
        entry.bubbleContainer = undefined;
      }
      bubbleContainer.destroy(true);
    });
  }

  private walkAgentTo(agentId: string, targetTileX: number, targetTileY: number, onArrival?: () => void) {
    const entry = this.agentSprites.get(agentId);
    if (!entry) return;

    const startTileX = Math.floor(entry.container.x / 16);
    const startTileY = Math.floor(entry.container.y / 16);

    this.pathfinder.findPath(startTileX, startTileY, targetTileX, targetTileY, (path) => {
      if (!path || path.length === 0) {
        onArrival?.();
        return;
      }

      entry.state = 'walking';
      let stepIndex = 0;

      const stepTimer = this.time.addEvent({
        delay: 120, // speed per tile
        repeat: path.length - 1,
        callback: () => {
          const pt = path[stepIndex];
          entry.container.setPosition(pt.x * 16 + 8, pt.y * 16 + 8);
          stepIndex++;
          if (stepIndex >= path.length) {
            entry.state = 'working';
            onArrival?.();
          }
        },
      });
    });
    this.pathfinder.calculate();
  }

  private triggerConfetti() {
    const emitter = this.add.particles(36 * 16, 20 * 16, 'confetti_particle', {
      speed: { min: 100, max: 250 },
      angle: { min: 0, max: 360 },
      scale: { start: 1.5, end: 0 },
      lifespan: 3000,
      gravityY: 150,
      quantity: 50,
    });
    this.time.delayedCall(4000, () => emitter.stop());
  }

  private processNewEvents(events: Array<{ id: number; type: string; agent_id?: string | null; payload: any }>) {
    if (!events || events.length === 0) return;

    // The store prepends events (newest first). Process every unseen event oldest first.
    const unseen = events
      .filter((event) => event.id > this.lastHandledEventIndex)
      .sort((a, b) => a.id - b.id);

    for (const event of unseen) {
      this.lastHandledEventIndex = Math.max(this.lastHandledEventIndex, event.id);

      if (event.type === 'agent.thinking' && event.agent_id) {
        this.showAgentBubble(event.agent_id, 'bubble_thinking');
      } else if (event.type === 'task.blocked' && event.agent_id) {
        this.showAgentBubble(event.agent_id, 'bubble_blocked', 5000);
      } else if (event.type === 'project.completed') {
        this.triggerConfetti();
      } else if (event.type === 'task.delegated' && event.agent_id && event.payload?.to_agent_id) {
        const delegator = event.agent_id;
        const targetAgent = this.agentSprites.get(event.payload.to_agent_id);
        if (targetAgent?.desk) {
          this.walkAgentTo(delegator, targetAgent.desk.tileX, targetAgent.desk.tileY, () => {
            const delegatorEntry = this.agentSprites.get(delegator);
            if (delegatorEntry?.desk) {
              this.walkAgentTo(delegator, delegatorEntry.desk.tileX, delegatorEntry.desk.tileY);
            }
          });
        }
      }
    }
  }

  update() {
    // 60 fps update loop
  }
}
