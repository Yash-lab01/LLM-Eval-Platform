"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3,
  Bot,
  Compass,
  History,
  PlayCircle,
  Terminal,
  Zap,
} from "lucide-react";
import { checkSystemHealth } from "@/lib/api";

const navItems = [
  { name: "Dashboard", href: "/", icon: Compass, id: "nav-dashboard" },
  { name: "Eval Runner", href: "/eval/new", icon: PlayCircle, id: "nav-eval-runner" },
  { name: "Leaderboard", href: "/leaderboard", icon: BarChart3, id: "nav-leaderboard" },
  { name: "Eval History", href: "/history", icon: History, id: "nav-history" },
  { name: "Prompt Library", href: "/prompts", icon: Terminal, id: "nav-prompts" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    checkSystemHealth()
      .then((res) => setIsHealthy(res.status === "healthy"))
      .catch(() => setIsHealthy(false));
  }, []);

  return (
    <aside className="w-64 bg-slate-900/90 border-r border-slate-800 flex flex-col justify-between p-4 min-h-screen text-slate-200">
      <div>
        {/* Brand Header */}
        <Link href="/" className="flex items-center gap-3 px-2 py-3 mb-6 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-base tracking-tight text-white flex items-center gap-1.5">
              LLM Eval <span className="text-xs bg-indigo-500/20 text-indigo-400 px-1.5 py-0.5 rounded font-mono">v0.1</span>
            </h1>
            <p className="text-xs text-slate-400">Benchmarking Engine</p>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                id={item.id}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-indigo-400" : "text-slate-400"}`} />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer System Status */}
      <div className="pt-4 border-t border-slate-800/80">
        <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800/60">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5 text-slate-400" /> API Gateway
            </span>
            <span
              className={`inline-flex items-center gap-1 font-mono text-[10px] px-1.5 py-0.5 rounded-full ${
                isHealthy === true
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                  : isHealthy === false
                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isHealthy === true
                    ? "bg-emerald-400 animate-pulse"
                    : isHealthy === false
                    ? "bg-rose-400"
                    : "bg-slate-500"
                }`}
              />
              {isHealthy === true ? "Online" : isHealthy === false ? "Degraded" : "Checking"}
            </span>
          </div>
          <p className="text-[11px] text-slate-500">FastAPI :8000 &bull; Redis DB 0</p>
        </div>
      </div>
    </aside>
  );
}
