import type { Metadata } from "next";
import "./globals.css";
import { LoginGate } from "@/components/LoginGate";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = { title: "AeroRamp Vision", description: "Airport turnaround and ramp-safety intelligence" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><LoginGate><Shell>{children}</Shell></LoginGate></body></html>;
}
