import { type ReactNode } from "react";
import { useLenis } from "../../hooks/useLenis";

export function LenisProvider({ children }: { children: ReactNode }) {
  useLenis();
  return <>{children}</>;
}
