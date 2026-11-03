export type LottiePlayer = {
  destroy: () => void;
  goToAndStop: (value: number, isFrame?: boolean) => void;
};

export type LottieRuntime = {
  loadAnimation: (options: {
    container: HTMLElement;
    renderer: 'svg' | 'canvas';
    loop: boolean;
    autoplay: boolean;
    animationData: Record<string, unknown>;
    rendererSettings?: Record<string, unknown>;
  }) => LottiePlayer;
};

declare global {
  interface Window {
    lottie?: LottieRuntime;
  }
}

let lottieRuntimePromise: Promise<LottieRuntime> | null = null;
let ceoAnimationPromise: Promise<Record<string, unknown>> | null = null;

export function loadLottieRuntime(): Promise<LottieRuntime> {
  if (window.lottie) return Promise.resolve(window.lottie);
  if (lottieRuntimePromise) return lottieRuntimePromise;

  lottieRuntimePromise = new Promise<LottieRuntime>((resolve, reject) => {
    let script = document.querySelector<HTMLScriptElement>('script[data-pixel-lottie]');
    if (!script) {
      script = document.createElement('script');
      script.src = '/vendor/lottie.min.js';
      script.dataset.pixelLottie = 'true';
      document.head.appendChild(script);
    }
    const onLoad = () => {
      if (window.lottie) resolve(window.lottie);
      else reject(new Error('Local avatar player did not initialize.'));
    };
    const onError = () => reject(new Error('Local avatar player is unavailable.'));
    script.addEventListener('load', onLoad, { once: true });
    script.addEventListener('error', onError, { once: true });
    if (window.lottie) resolve(window.lottie);
  }).catch((error) => {
    lottieRuntimePromise = null;
    throw error;
  });

  return lottieRuntimePromise;
}

export function loadCeoAnimation(): Promise<Record<string, unknown>> {
  if (!ceoAnimationPromise) {
    ceoAnimationPromise = fetch('/avatars/ceo-with-wavy-hair-and-a-beard.json')
      .then((response) => {
        if (!response.ok) throw new Error('CEO animation could not be loaded.');
        return response.json() as Promise<Record<string, unknown>>;
      })
      .catch((error) => {
        ceoAnimationPromise = null;
        throw error;
      });
  }
  return ceoAnimationPromise;
}
