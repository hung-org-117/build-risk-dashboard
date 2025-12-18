'use client'

import { type ReactNode } from 'react'

import { RequireAdmin } from '@/components/auth/RequireAdmin'

export default function AdminLayout({ children }: { children: ReactNode }) {
    return <RequireAdmin>{children}</RequireAdmin>
}
