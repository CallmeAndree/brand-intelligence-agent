"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  {
    href: "/",
    label: "Dashboard",
    activeClass: "bg-[#1a3a3a] text-white shadow-sm shadow-ink/10",
    inactiveClass: "bg-[#dff5ef] text-[#1a3a3a] hover:bg-[#c8eee5]",
  },
  {
    href: "/monitor",
    label: "Monitor",
    activeClass: "bg-[#b8a4ed] text-white shadow-sm shadow-ink/10",
    inactiveClass: "bg-[#efe9ff] text-[#4b3b83] hover:bg-[#e4d9ff]",
  },
  {
    href: "/chat",
    label: "Chat",
    activeClass: "bg-[#ffb084] text-ink shadow-sm shadow-ink/10",
    inactiveClass: "bg-[#fff0e7] text-[#8a3d17] hover:bg-[#ffe2d1]",
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function TabNav() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 bg-canvas/95 backdrop-blur supports-[backdrop-filter]:bg-canvas/85">
      <div className="relative mx-auto flex max-w-content items-center justify-center px-4 py-3">
        <Link
          href="/"
          aria-label="ZaloPay Brand Intelligence"
          className="absolute left-4 flex items-center gap-2"
        >
          <Image
            src="/logo.png"
            alt="ZaloPay"
            width={36}
            height={36}
            priority
            className="h-9 w-9 rounded-[10px]"
          />
          <span className="hidden text-sm font-semibold tracking-tight text-ink sm:inline">
            Brand Intelligence
          </span>
        </Link>
        <div className="inline-flex items-center justify-center gap-2 rounded-full bg-white/45 p-1.5 shadow-sm ring-1 ring-ink/5">
          {TABS.map((tab) => {
            const active = isActive(pathname, tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`inline-flex min-w-28 items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition ${
                  active ? tab.activeClass : tab.inactiveClass
                }`}
                aria-current={active ? "page" : undefined}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
