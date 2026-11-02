import Phaser from 'phaser';
import { AssetPack } from './types';

export class ProceduralPixelArtPack implements AssetPack {
  generateTextures(scene: Phaser.Scene): void {
    const tileSize = 16;

    // Helper to generate a 16x16 canvas texture
    const makeTexture = (
      key: string,
      drawFn: (ctx: CanvasRenderingContext2D, width: number, height: number) => void,
      width = tileSize,
      height = tileSize
    ) => {
      if (scene.textures.exists(key)) return;
      const canvas = scene.textures.createCanvas(key, width, height);
      if (!canvas) return;
      const ctx = canvas.getContext();
      ctx.imageSmoothingEnabled = false;
      drawFn(ctx, width, height);
      canvas.refresh();
    };

    // 1. Office Floor Light
    makeTexture('tile_floor_light', (ctx) => {
      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(0, 0, 16, 16);
      ctx.fillStyle = '#e2e8f0';
      ctx.fillRect(0, 0, 8, 8);
      ctx.fillRect(8, 8, 8, 8);
      ctx.fillStyle = '#94a3b8';
      ctx.strokeRect(0.5, 0.5, 15, 15);
    });

    // 2. Office Floor Dark
    makeTexture('tile_floor_dark', (ctx) => {
      ctx.fillStyle = '#94a3b8';
      ctx.fillRect(0, 0, 16, 16);
      ctx.fillStyle = '#a8b6c8';
      ctx.fillRect(0, 0, 8, 8);
      ctx.fillRect(8, 8, 8, 8);
      ctx.fillStyle = '#64748b';
      ctx.strokeRect(0.5, 0.5, 15, 15);
    });

    // 3. Wall Tile
    makeTexture('tile_wall', (ctx) => {
      ctx.fillStyle = '#334155';
      ctx.fillRect(0, 0, 16, 16);
      ctx.fillStyle = '#475569';
      ctx.fillRect(1, 1, 14, 7);
      ctx.fillRect(1, 9, 14, 6);
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(0, 8, 16, 1);
    });

    // 4. Desk Furniture (16x16)
    makeTexture('furniture_desk', (ctx) => {
      ctx.fillStyle = '#78350f'; // mahogany wood
      ctx.fillRect(1, 2, 14, 12);
      ctx.fillStyle = '#92400e';
      ctx.fillRect(2, 3, 12, 10);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(2, 12, 2, 2);
      ctx.fillRect(12, 12, 2, 2);
    });

    // 5. Computer Monitor on Desk
    makeTexture('furniture_computer', (ctx) => {
      // Monitor stand
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(6, 10, 4, 3);
      // Monitor frame
      ctx.fillRect(3, 2, 10, 8);
      // Glowing retro screen (cyan phosphor)
      ctx.fillStyle = '#06b6d4';
      ctx.fillRect(4, 3, 8, 6);
      // Cursor blink
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(5, 5, 2, 2);
    });

    // 6. Office Chair
    makeTexture('furniture_chair', (ctx) => {
      ctx.fillStyle = '#0284c7';
      ctx.fillRect(3, 3, 10, 10);
      ctx.fillStyle = '#0369a1';
      ctx.fillRect(4, 4, 8, 8);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(7, 13, 2, 3);
    });

    // 7. Potted Plant
    makeTexture('furniture_plant', (ctx) => {
      // Pot
      ctx.fillStyle = '#b45309';
      ctx.fillRect(4, 9, 8, 7);
      // Foliage
      ctx.fillStyle = '#15803d';
      ctx.fillRect(3, 2, 10, 7);
      ctx.fillStyle = '#22c55e';
      ctx.fillRect(5, 1, 6, 5);
    });

    // 8. Watercooler
    makeTexture('furniture_watercooler', (ctx) => {
      // Water jug
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(5, 1, 6, 6);
      // Dispenser body
      ctx.fillStyle = '#e2e8f0';
      ctx.fillRect(4, 7, 8, 9);
      // Tap
      ctx.fillStyle = '#ef4444';
      ctx.fillRect(7, 9, 2, 2);
    });

    // 9. Document / Paper Item
    makeTexture('item_paper', (ctx) => {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(3, 2, 10, 12);
      ctx.fillStyle = '#94a3b8';
      ctx.fillRect(5, 5, 6, 1);
      ctx.fillRect(5, 8, 6, 1);
      ctx.fillRect(5, 11, 4, 1);
    });

    // 10. Thinking Speech Bubble
    makeTexture('bubble_thinking', (ctx) => {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(1, 1, 14, 11);
      ctx.fillStyle = '#0f172a';
      ctx.strokeRect(0.5, 0.5, 15, 12);
      // Three dots
      ctx.fillRect(3, 5, 2, 2);
      ctx.fillRect(7, 5, 2, 2);
      ctx.fillRect(11, 5, 2, 2);
    });

    // 11. Blocked Speech Bubble (!)
    makeTexture('bubble_blocked', (ctx) => {
      ctx.fillStyle = '#fee2e2';
      ctx.fillRect(1, 1, 14, 12);
      ctx.fillStyle = '#dc2626';
      ctx.strokeRect(0.5, 0.5, 15, 13);
      // Exclamation mark
      ctx.fillRect(7, 3, 2, 5);
      ctx.fillRect(7, 10, 2, 2);
    });

    // 12. Confetti Particle
    makeTexture('confetti_particle', (ctx) => {
      ctx.fillStyle = '#f59e0b';
      ctx.fillRect(0, 0, 4, 4);
    }, 4, 4);

    // 13. Dynamic Character Sprites
    // Generates base 16x16 humanoid template with head, eyes, torso, legs
    makeTexture('char_base_template', (ctx) => {
      // Head
      ctx.fillStyle = '#fbcfe8';
      ctx.fillRect(5, 2, 6, 5);
      // Eyes
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(6, 4, 1, 1);
      ctx.fillRect(9, 4, 1, 1);
      // Torso / Shirt
      ctx.fillStyle = '#3b82f6';
      ctx.fillRect(4, 7, 8, 5);
      // Legs / Pants
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(5, 12, 2, 4);
      ctx.fillRect(9, 12, 2, 4);
    });
  }

  // Generates a customized 16x16 agent character texture based on role metadata
  createCustomAgentTexture(
    scene: Phaser.Scene,
    key: string,
    shirtColor: string,
    skinTone: number,
    level: number,
    isCeo: boolean
  ): string {
    if (scene.textures.exists(key)) return key;

    const skinTones = ['#fde047', '#fed7aa', '#fbcfe8', '#d4a373', '#8d5b4c'];
    const skinHex = skinTones[(skinTone - 1) % skinTones.length] || '#fed7aa';

    const canvas = scene.textures.createCanvas(key, 16, 16);
    if (!canvas) return 'char_base_template';

    const ctx = canvas.getContext();
    ctx.imageSmoothingEnabled = false;

    // Hair
    ctx.fillStyle = '#451a03';
    ctx.fillRect(4, 1, 8, 3);

    // Face / Head
    ctx.fillStyle = skinHex;
    ctx.fillRect(5, 3, 6, 4);

    // Eyes
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(6, 4, 1, 1);
    ctx.fillRect(9, 4, 1, 1);

    // Shirt / Department Uniform
    ctx.fillStyle = shirtColor;
    ctx.fillRect(4, 7, 8, 5);

    // Manager Tie or CEO Crown
    if (isCeo) {
      // Golden Crown on head
      ctx.fillStyle = '#f59e0b';
      ctx.fillRect(5, 0, 6, 2);
      ctx.fillRect(5, 0, 1, 1);
      ctx.fillRect(7, 0, 2, 1);
      ctx.fillRect(10, 0, 1, 1);
    } else if (level <= 3) {
      // Tie
      ctx.fillStyle = '#ef4444';
      ctx.fillRect(7, 7, 2, 4);
    }

    // Pants
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(5, 12, 2, 4);
    ctx.fillRect(9, 12, 2, 4);

    canvas.refresh();
    return key;
  }
}

export const proceduralPixelArt = new ProceduralPixelArtPack();
