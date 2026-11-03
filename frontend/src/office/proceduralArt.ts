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

  // Generates a distinct 24px pixel portrait from each agent's stable identity.
  createCustomAgentTexture(
    scene: Phaser.Scene,
    key: string,
    shirtColor: string,
    skinTone: number,
    level: number,
    isCeo: boolean,
    hairStyle = 1,
    accessory = 'id_badge',
    agentId = key
  ): string {
    if (scene.textures.exists(key)) return key;

    const rootStyle = typeof window !== 'undefined' ? window.getComputedStyle(document.documentElement) : null;
    const token = (name: string, fallback: string) => rootStyle?.getPropertyValue(name).trim() || fallback;
    const skinPalette = [
      token('--pixel-avatar-skin-1', '#e9b78e'),
      token('--pixel-avatar-skin-2', '#d99b70'),
      token('--pixel-avatar-skin-3', '#a96d4f'),
      token('--pixel-avatar-skin-4', '#704634'),
      token('--pixel-avatar-skin-5', '#f2c6a0'),
    ];
    const hairPalette = [
      token('--pixel-avatar-hair-1', '#2d211e'),
      token('--pixel-avatar-hair-2', '#493126'),
      token('--pixel-avatar-hair-3', '#171b24'),
      token('--pixel-avatar-hair-4', '#8a4d2d'),
      token('--pixel-avatar-hair-5', '#c1b8a8'),
      token('--pixel-avatar-hair-6', '#512d54'),
    ];
    const seed = Array.from(agentId).reduce((value, char) => (value * 31 + char.charCodeAt(0)) >>> 0, 7);
    const skin = skinPalette[Math.max(0, skinTone - 1) % skinPalette.length];
    const hair = hairPalette[(seed + hairStyle) % hairPalette.length];
    const style = Math.max(1, hairStyle + (seed % 3));
    const canvas = scene.textures.createCanvas(key, 24, 24);
    if (!canvas) return 'char_base_template';

    const ctx = canvas.getContext();
    ctx.imageSmoothingEnabled = false;

    // Neck and shirt
    ctx.fillStyle = skin;
    ctx.fillRect(10, 13, 4, 4);
    ctx.fillStyle = shirtColor;
    ctx.fillRect(5, 16, 14, 8);
    ctx.fillRect(3, 19, 3, 5);
    ctx.fillRect(18, 19, 3, 5);

    // Face and ears
    ctx.fillStyle = skin;
    ctx.fillRect(7, 6, 10, 9);
    ctx.fillRect(6, 9, 1, 3);
    ctx.fillRect(17, 9, 1, 3);

    // Hair silhouettes vary by seeded style.
    ctx.fillStyle = hair;
    if (style % 6 === 1) {
      ctx.fillRect(6, 4, 12, 4);
      ctx.fillRect(5, 6, 3, 4);
      ctx.fillRect(16, 6, 3, 4);
      ctx.fillRect(8, 3, 7, 2);
    } else if (style % 6 === 2) {
      ctx.fillRect(6, 3, 12, 5);
      ctx.fillRect(5, 6, 3, 9);
      ctx.fillRect(16, 6, 3, 9);
      ctx.fillRect(7, 2, 4, 2);
      ctx.fillRect(14, 2, 3, 2);
    } else if (style % 6 === 3) {
      ctx.fillRect(6, 5, 12, 4);
      ctx.fillRect(5, 7, 3, 3);
      ctx.fillRect(16, 7, 3, 3);
      ctx.fillRect(7, 3, 3, 3);
      ctx.fillRect(11, 2, 4, 3);
      ctx.fillRect(16, 4, 2, 3);
    } else if (style % 6 === 4) {
      ctx.fillRect(6, 4, 12, 4);
      ctx.fillRect(5, 7, 3, 8);
      ctx.fillRect(16, 7, 3, 8);
      ctx.fillRect(8, 3, 8, 2);
      ctx.fillRect(10, 7, 4, 2);
    } else if (style % 6 === 5) {
      ctx.fillRect(6, 5, 12, 4);
      ctx.fillRect(5, 7, 3, 5);
      ctx.fillRect(16, 7, 3, 5);
      ctx.fillRect(9, 1, 6, 4);
      ctx.fillRect(8, 3, 8, 2);
    } else {
      ctx.fillRect(6, 4, 12, 5);
      ctx.fillRect(5, 7, 3, 8);
      ctx.fillRect(16, 7, 3, 8);
      ctx.fillRect(8, 2, 8, 3);
    }

    // Eyes, nose and expression
    ctx.fillStyle = token('--color-paper-3', '#17202a');
    ctx.fillRect(9, 10, 2, 1);
    ctx.fillRect(14, 10, 2, 1);
    ctx.fillStyle = token('--pixel-avatar-line', '#633f32');
    ctx.fillRect(11, 13, 3, 1);

    // Distinct beard and eyewear details
    if (seed % 4 === 0 || accessory.includes('beard')) {
      ctx.fillStyle = hair;
      ctx.fillRect(8, 13, 2, 2);
      ctx.fillRect(14, 13, 2, 2);
      ctx.fillRect(10, 14, 5, 2);
    }
    if (seed % 7 === 0 || accessory.includes('glasses')) {
      ctx.strokeStyle = token('--color-paper-3', '#17202a');
      ctx.lineWidth = 1;
      ctx.strokeRect(8, 9, 4, 3);
      ctx.strokeRect(13, 9, 4, 3);
      ctx.fillRect(12, 10, 1, 1);
    }

    // Accessories and role signals
    if (isCeo) {
      ctx.fillStyle = token('--color-accent', '#e5b84b');
      ctx.fillRect(7, 1, 10, 2);
      ctx.fillRect(7, 0, 2, 2);
      ctx.fillRect(11, 0, 2, 2);
      ctx.fillRect(15, 0, 2, 2);
    } else if (level <= 3 || accessory.includes('tie')) {
      ctx.fillStyle = token('--color-accent', '#e5b84b');
      ctx.fillRect(11, 16, 2, 5);
      ctx.fillRect(10, 16, 4, 1);
    } else if (accessory.includes('head') || seed % 9 === 0) {
      ctx.strokeStyle = token('--color-cool', '#82a9d6');
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(12, 9, 9, Math.PI, Math.PI * 2);
      ctx.stroke();
    } else {
      ctx.fillStyle = token('--color-cool', '#82a9d6');
      ctx.fillRect(17, 17, 2, 3);
    }

    canvas.refresh();
    return key;
  }
}

export const proceduralPixelArt = new ProceduralPixelArtPack();
