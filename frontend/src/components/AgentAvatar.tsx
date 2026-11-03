import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Agent } from '../api/types';
import { loadCeoAnimation, loadLottieRuntime, LottiePlayer } from '../lib/lottie';

const SKIN_TONES = ['var(--pixel-avatar-skin-1)', 'var(--pixel-avatar-skin-2)', 'var(--pixel-avatar-skin-3)', 'var(--pixel-avatar-skin-4)', 'var(--pixel-avatar-skin-5)'];
const HAIR_TONES = ['var(--pixel-avatar-hair-1)', 'var(--pixel-avatar-hair-2)', 'var(--pixel-avatar-hair-3)', 'var(--pixel-avatar-hair-4)', 'var(--pixel-avatar-hair-5)', 'var(--pixel-avatar-hair-6)'];

function hash(value: string): number {
  let result = 2166136261;
  for (let i = 0; i < value.length; i++) result = Math.imul(result ^ value.charCodeAt(i), 16777619);
  return result >>> 0;
}

function AvatarPortrait({ agent, size }: { agent: Agent; size: number }) {
  const seed = hash(agent.id || agent.role_key);
  const style = agent.sprite_json?.hair_style || (seed % 6) + 1;
  const skin = SKIN_TONES[((agent.sprite_json?.skin_tone || 2) - 1) % SKIN_TONES.length];
  const hair = HAIR_TONES[seed % HAIR_TONES.length];
  const shirt = agent.sprite_json?.shirt_color || 'var(--color-cool)';
  const faceShape = seed % 3;
  const hairPaths = [
    'M9 18V13L12 7L18 5L27 7L31 13V19L27 14L23 12L18 14L13 12L9 18Z',
    'M9 17V11L14 6L25 6L31 12V18L28 16L27 10L22 13L16 11L12 17Z',
    'M8 18V12L12 6L20 4L28 8L32 14V20L28 15L24 14L20 16L15 13L11 19Z',
    'M10 18V10L15 5L25 5L30 10V17L26 14L23 12L18 14L13 12Z',
    'M8 19V12L12 6L18 4L26 6L32 13V20L28 15L25 18L22 12L18 16L14 12L11 20Z',
    'M9 18V12L13 7L20 5L27 7L31 13V19L27 15L24 12L19 13L14 11Z',
  ];
  const beard = seed % 5 === 0 || style === 6;
  const glasses = seed % 7 === 0 || style === 4;
  const accessory = agent.sprite_json?.accessory || '';
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label={agent.display_name + ' avatar'} shapeRendering="crispEdges">
      <rect x="1" y="1" width="38" height="38" rx="7" fill="var(--color-paper-3)" stroke="var(--color-rule)" />
      <path d="M5 40V34L10 28H30L35 34V40Z" fill={shirt} />
      <path d={faceShape === 0 ? 'M12 12H28V25L24 30H16L12 25Z' : faceShape === 1 ? 'M13 10H27V25L23 30H17L13 25Z' : 'M11 13H29V24L24 31H16L11 24Z'} fill={skin} />
      <path d={hairPaths[(style - 1) % hairPaths.length]} fill={hair} />
      <rect x="15" y="19" width="2" height="2" fill="var(--color-paper-3)" />
      <rect x="24" y="19" width="2" height="2" fill="var(--color-paper-3)" />
      <path d="M18 25H22" stroke="var(--pixel-avatar-line)" strokeWidth="1.5" />
      {beard && <path d="M14 24L16 29L20 31L24 29L27 24L25 27H15Z" fill={hair} />}
      {glasses && <g fill="none" stroke="var(--color-paper-3)" strokeWidth="1.2"><rect x="12.5" y="17" width="7" height="5" rx="1" /><rect x="21" y="17" width="7" height="5" rx="1" /><path d="M19.5 19H21" /></g>}
      {accessory.includes('tie') && <path d="M18 30H22L21 34L20 36L19 34Z" fill="var(--color-accent)" />}
      {agent.role_key === 'ceo' && <path d="M14 7L16 3L20 6L24 3L26 7Z" fill="var(--color-accent)" />}
      {accessory.includes('head') && <path d="M8 20V14Q8 5 20 5Q32 5 32 14V20" fill="none" stroke="var(--color-cool)" strokeWidth="2" />}
    </svg>
  );
}

export const AgentAvatar: React.FC<{ agent: Agent; size?: number; className?: string }> = ({ agent, size = 44, className = '' }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [animationReady, setAnimationReady] = useState(false);
  const isCeo = agent.role_key === 'ceo';
  const fallback = useMemo(() => <AvatarPortrait agent={agent} size={size} />, [agent, size]);

  useEffect(() => {
    if (!isCeo || !containerRef.current) return;
    let cancelled = false;
    let player: LottiePlayer | undefined;

    const mountAnimation = async () => {
      const [runtime, animationData] = await Promise.all([
        loadLottieRuntime(),
        loadCeoAnimation(),
      ]);
      if (cancelled || !containerRef.current) return;

      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      player = runtime.loadAnimation({
        container: containerRef.current,
        renderer: 'svg',
        loop: !reduceMotion,
        autoplay: !reduceMotion,
        animationData,
      });
      if (reduceMotion) player.goToAndStop(0, true);
      setAnimationReady(true);
    };

    void mountAnimation().catch(() => {
      if (!cancelled) setAnimationReady(false);
    });
    return () => {
      cancelled = true;
      player?.destroy();
      setAnimationReady(false);
    };
  }, [isCeo]);

  if (!isCeo) {
    return <span className={'agent-avatar ' + className} style={{ width: size, height: size }}>{fallback}</span>;
  }

  return (
    <span className={'agent-avatar agent-avatar-ceo ' + className} style={{ width: size, height: size }}>
      <span className="agent-avatar-fallback">{fallback}</span>
      <span ref={containerRef} className="agent-avatar-animation" aria-hidden="true" data-ready={animationReady} />
    </span>
  );
};
