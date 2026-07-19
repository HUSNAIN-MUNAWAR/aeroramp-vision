"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PropsWithChildren } from "react";
import { logout } from "@/lib/api";

const links = [
  ["/", "Operations"],
  ["/turnarounds", "Turnarounds"],
  ["/alerts", "Alert center"],
  ["/incidents", "Incident review"],
  ["/cameras", "Cameras & zones"],
  ["/models", "Model registry"],
  ["/reports", "Reports"],
  ["/health", "System health"],
];

export function Shell({ children }: PropsWithChildren) {
  const path = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">AR</span><div><strong>AeroRamp Vision</strong><small>Ramp intelligence control</small></div></div>
        <nav>{links.map(([href, label]) => <Link key={href} href={href} className={path === href || (href !== "/" && path.startsWith(href)) ? "active" : ""}>{label}</Link>)}</nav>
        <div className="sidebar-footer">
          <div className="decision-badge">Decision support only</div>
          <button className="ghost-button" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main"><header className="topbar"><div><span className="eyebrow">AIRPORT OPERATIONS</span><h1>{links.find(([href]) => href === path)?.[1] ?? "Operational detail"}</h1></div><div className="live-indicator"><span /> Connected</div></header>{children}</main>
    </div>
  );
}
