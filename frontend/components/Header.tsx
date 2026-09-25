"use client";

import Link from "next/link";
import { PlayCircle, Sparkles } from "lucide-react";

interface HeaderProps {
  title: string;
  description?: string;
  showNewEvalButton?: boolean;
}

export default function Header({
  title,
  description,
  showNewEvalButton = true,
}: HeaderProps) {
  return (
    <header className="flex items-center justify-between pb-6 mb-6 border-b border-slate-800/80">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-slate-400 mt-1">{description}</p>
        )}
      </div>

      {showNewEvalButton && (
        <Link
          href="/eval/new"
          id="btn-header-new-eval"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-r from-indigo-500 to-cyan-500 hover:from-indigo-600 hover:to-cyan-600 text-white shadow-lg shadow-indigo-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
        >
          <PlayCircle className="w-4 h-4" />
          <span>New Benchmark</span>
          <Sparkles className="w-3.5 h-3.5 text-cyan-200" />
        </Link>
      )}
    </header>
  );
}
