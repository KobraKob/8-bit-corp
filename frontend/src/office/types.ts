export type AgentActionState =
  | 'idle'
  | 'walking'
  | 'working'
  | 'thinking'
  | 'in_meeting'
  | 'reviewing'
  | 'blocked'
  | 'celebrating'
  | 'break';

export interface DeskPosition {
  deskId: string;
  agentId?: string;
  department: string;
  tileX: number;
  tileY: number;
  facing: 'up' | 'down' | 'left' | 'right';
}

export interface DepartmentRoom {
  name: string;
  bounds: { x: number; y: number; width: number; height: number };
  floorColor: number;
  wallColor: number;
  desks: DeskPosition[];
}

export interface BuildingLayout {
  gridWidth: number;
  gridHeight: number;
  tileSize: number;
  rooms: DepartmentRoom[];
  collisionMatrix: number[][]; // 0 = walkable, 1 = obstacle
  lobbyDesk: { tileX: number; tileY: number };
  breakRoom: { tileX: number; tileY: number };
}

export interface AssetPack {
  generateTextures(scene: Phaser.Scene): void;
}
