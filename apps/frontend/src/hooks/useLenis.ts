import { useEffect, useRef } from "react";
import Lenis from "lenis";

/**
 * Returns nothing; mounts Lenis smooth-scroll on <html> and tears it down on unmount.
 * The LenisProvider component calls this internally — exported in case other
 * components need a stable Lenis ref.
 */
export function useLenis() {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
    });
    lenisRef.current = lenis;

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    return () => {
      lenis.destroy();
    };
  }, []);

  return lenisRef;
}
