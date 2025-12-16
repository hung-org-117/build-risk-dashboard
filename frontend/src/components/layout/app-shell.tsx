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
    <div className="grid h-screen w-full overflow-hidden bg-slate-50 text-slate-900 lg:grid-cols-[280px_1fr] dark:bg-slate-950 dark:text-slate-50">
      {/* Desktop Sidebar - Fixed */}
      <aside className="hidden lg:block h-screen overflow-hidden border-r dark:border-slate-800">
        <Sidebar />
      </aside>

      {/* Mobile Sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-72 transform border-r bg-white shadow-xl transition-transform duration-200 ease-in-out dark:border-slate-800 dark:bg-slate-950 lg:hidden',
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <Sidebar />
      </div>
      {mobileNavOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={closeMobileNav}
          aria-hidden="true"
        />
      ) : null}

      {/* Main Content Area */}
      <div className="flex flex-col h-screen overflow-hidden">
        <Topbar onToggleSidebar={() => setMobileNavOpen((prev) => !prev)} />
        <main className="flex-1 overflow-y-auto bg-slate-50 p-4 lg:p-6 dark:bg-slate-950">
          <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 lg:gap-6">{children}</div>
        </main>
      </div>
    </div>
  )
}
