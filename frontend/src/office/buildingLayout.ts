import { Agent } from '../api/types';
import { BuildingLayout, DepartmentRoom, DeskPosition } from './types';

export function generateBuildingLayout(agents: Agent[]): BuildingLayout {
  const tileSize = 16;
  const gridWidth = 72; // in tiles
  const gridHeight = 56; // in tiles

  // Initialize collision matrix: 0 = walkable, 1 = obstacle
  const collisionMatrix: number[][] = Array.from({ length: gridHeight }, () =>
    Array.from({ length: gridWidth }, () => 0)
  );

  // Group agents by department
  const agentsByDept: Record<string, Agent[]> = {};
  for (const a of agents) {
    if (!agentsByDept[a.department]) {
      agentsByDept[a.department] = [];
    }
    agentsByDept[a.department].push(a);
  }

  // Define Room Layout specifications
  const roomDefs = [
    // Top Floor: Executive Suite & Boardroom
    { name: 'Executive', x: 2, y: 2, w: 32, h: 10, floorColor: 0x334155, wallColor: 0xca8a04 },
    { name: 'Boardroom', x: 36, y: 2, w: 34, h: 10, floorColor: 0x1e293b, wallColor: 0xca8a04 },

    // Middle Floor: Engineering & Design
    { name: 'Engineering', x: 2, y: 14, w: 36, h: 13, floorColor: 0x064e3b, wallColor: 0x10b981 },
    { name: 'Design', x: 40, y: 14, w: 30, h: 13, floorColor: 0x831843, wallColor: 0xec4899 },

    // Lower Floor: Marketing, Content, Research, Finance
    { name: 'Marketing', x: 2, y: 29, w: 16, h: 12, floorColor: 0x7c2d12, wallColor: 0xf97316 },
    { name: 'Content', x: 20, y: 29, w: 16, h: 12, floorColor: 0x581c87, wallColor: 0x8b5cf6 },
    { name: 'Research', x: 38, y: 29, w: 16, h: 12, floorColor: 0x164e63, wallColor: 0x06b6d4 },
    { name: 'Finance', x: 56, y: 29, w: 14, h: 12, floorColor: 0x365314, wallColor: 0x84cc16 },

    // Ground Floor: Lobby / Intake, Support Wing, Breakroom
    { name: 'Lobby', x: 2, y: 43, w: 26, h: 11, floorColor: 0x475569, wallColor: 0x64748b },
    { name: 'Support', x: 30, y: 43, w: 22, h: 11, floorColor: 0x334155, wallColor: 0x94a3b8 },
    { name: 'Breakroom', x: 54, y: 43, w: 16, h: 11, floorColor: 0x1e293b, wallColor: 0x38bdf8 },
  ];

  const rooms: DepartmentRoom[] = [];

  for (const def of roomDefs) {
    const desks: DeskPosition[] = [];
    const deptAgents = agentsByDept[def.name] || [];

    // Mark walls as obstacles (with door openings)
    const doorX = def.x + Math.floor(def.w / 2);
    for (let x = def.x; x < def.x + def.w; x++) {
      for (let y = def.y; y < def.y + def.h; y++) {
        const isWall =
          x === def.x || x === def.x + def.w - 1 || y === def.y || y === def.y + def.h - 1;
        const isDoor = (x === doorX || x === doorX + 1) && y === def.y + def.h - 1;

        if (isWall && !isDoor) {
          collisionMatrix[y][x] = 1; // Obstacle wall
        }
      }
    }

    // Place desks inside the room in neat rows
    let currentX = def.x + 3;
    let currentY = def.y + 3;
    const maxAgentsToPlace = Math.max(deptAgents.length, 2);

    for (let i = 0; i < maxAgentsToPlace; i++) {
      const assignedAgent = deptAgents[i];
      desks.push({
        deskId: `desk_${def.name}_${i}`,
        agentId: assignedAgent?.id,
        department: def.name,
        tileX: currentX,
        tileY: currentY,
        facing: 'down',
      });

      // Desk tiles remain walkable: agents stand here and use them as path endpoints.

      currentX += 4;
      if (currentX > def.x + def.w - 4) {
        currentX = def.x + 3;
        currentY += 4;
      }
    }

    rooms.push({
      name: def.name,
      bounds: { x: def.x, y: def.y, width: def.w, height: def.h },
      floorColor: def.floorColor,
      wallColor: def.wallColor,
      desks,
    });
  }

  // Lobby intake desk (where client task enters)
  const lobbyDesk = { tileX: 14, tileY: 48 };
  // Breakroom watercooler
  const breakRoom = { tileX: 62, tileY: 48 };

  return {
    gridWidth,
    gridHeight,
    tileSize,
    rooms,
    collisionMatrix,
    lobbyDesk,
    breakRoom,
  };
}
