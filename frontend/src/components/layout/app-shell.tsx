'use client'

import { useState } from 'react'

import { cn } from '@/lib/utils'
import { Sidebar } from './sidebar'
import { Topbar } from './topbar'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const closeMobileNav = () => setMobileNavOpen(false)

  return (
    <div className="grid h-screen w-full overflow-hidden bg-slate-50 text-slate-900 md:grid-cols-[64px_1fr] lg:grid-cols-[280px_1fr] dark:bg-slate-950 dark:text-slate-50">
      {/* Tablet Sidebar - Icon only (md breakpoint) */}
      <aside className="hidden md:block lg:hidden h-screen overflow-hidden border-r dark:border-slate-800">
        <Sidebar collapsed />
      </aside>

      {/* Desktop/Laptop Sidebar - Full (lg+ breakpoint) */}
      <aside className="hidden lg:block h-screen overflow-hidden border-r dark:border-slate-800">
        <Sidebar />
      </aside>

      {/* Mobile Sidebar - Overlay */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-72 transform border-r bg-white shadow-xl transition-transform duration-200 ease-in-out dark:border-slate-800 dark:bg-slate-950 md:hidden',
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <Sidebar />
      </div>
      {mobileNavOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={closeMobileNav}
          aria-hidden="true"
        />
      ) : null}

      {/* Main Content Area */}
      <div className="flex flex-col h-screen overflow-hidden">
        <Topbar onToggleSidebar={() => setMobileNavOpen((prev) => !prev)} />
        <main className="flex-1 overflow-y-auto bg-slate-50 p-3 md:p-4 lg:p-6 dark:bg-slate-950">
          <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-3 md:gap-4 lg:gap-6">{children}</div>
        </main>
      </div>
    </div>
  )
}

