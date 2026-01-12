'use client'

import { useState, useEffect, useCallback } from 'react'
import { Users, Trash2, Shield, User, RefreshCw, Mail, Search } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { toast } from '@/components/ui/use-toast'
import { DataTable, type DataTableColumn } from '@/components/ui/data-table'
import { adminUsersApi, usersApi } from '@/lib/api'
import { formatDateTime } from '@/lib/utils'
import type { UserAccount } from '@/types'

export default function AdminUsersPage() {
    const [users, setUsers] = useState<UserAccount[]>([])
    const [totalUsers, setTotalUsers] = useState(0)
    const [currentUserId, setCurrentUserId] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')

    // Pagination
    const [page, setPage] = useState(1)
    const pageSize = 20

    // Delete dialog state
    const [deleteUserId, setDeleteUserId] = useState<string | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)

    const fetchCurrentUser = useCallback(async () => {
        try {
            const currentUser = await usersApi.getCurrentUser()
            setCurrentUserId(currentUser.id)
        } catch (err) {
            console.error('Failed to get current user:', err)
        }
    }, [])

    const fetchUsers = useCallback(async () => {
        setIsLoading(true)
        try {
            const response = await adminUsersApi.list(searchQuery || undefined, page, pageSize)
            setUsers(response.items)
            setTotalUsers(response.total)
        } catch (err) {
            console.error('Failed to load users:', err)
            toast({
                title: 'Error',
                description: 'Failed to load users',
                variant: 'destructive',
            })
        } finally {
            setIsLoading(false)
        }
    }, [searchQuery, page])

    useEffect(() => {
        fetchCurrentUser()
    }, [fetchCurrentUser])

    useEffect(() => {
        setPage(1) // Reset to page 1 when search changes
    }, [searchQuery])

    useEffect(() => {
        fetchUsers()
    }, [fetchUsers])

    const handleDeleteUser = async () => {
        if (!deleteUserId) return

        setIsDeleting(true)
        try {
            await adminUsersApi.delete(deleteUserId)
            setDeleteUserId(null)
            fetchUsers()
            toast({ title: 'Success', description: 'User deleted successfully' })
        } catch (err) {
            console.error('Failed to delete user:', err)
            toast({
                title: 'Error',
                description: 'Failed to delete user',
                variant: 'destructive',
            })
        } finally {
            setIsDeleting(false)
        }
    }

    const columns: DataTableColumn<UserAccount>[] = [
        {
            key: 'user',
            header: 'User',
            render: (user) => (
                <div className="flex items-center gap-2">
                    {user.github?.avatar_url ? (
                        <img
                            src={user.github.avatar_url}
                            alt={user.name || user.email}
                            className="h-8 w-8 rounded-full"
                        />
                    ) : (
                        <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                            <User className="h-4 w-4 text-muted-foreground" />
                        </div>
                    )}
                    <span>{user.name || user.github?.login || '-'}</span>
                    {user.id === currentUserId && (
                        <Badge variant="outline" className="text-xs">You</Badge>
                    )}
                </div>
            ),
        },
        {
            key: 'email',
            header: 'Email',
            render: (user) => (
                <div className="flex items-center gap-1 text-muted-foreground">
                    <Mail className="h-3 w-3" />
                    <span className="text-sm">{user.email}</span>
                </div>
            ),
        },
        {
            key: 'role',
            header: 'Role',
            render: (user) => (
                <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                    {user.role === 'admin' ? (
                        <Shield className="h-3 w-3 mr-1" />
                    ) : (
                        <User className="h-3 w-3 mr-1" />
                    )}
                    {user.role}
                </Badge>
            ),
        },
        {
            key: 'created_at',
            header: 'Created',
            render: (user) => (
                <span className="text-muted-foreground text-sm">
                    {formatDateTime(user.created_at)}
                </span>
            ),
        },
    ]

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Users className="h-6 w-6 text-muted-foreground" />
                    <div>
                        <h1 className="text-2xl font-bold">User Management</h1>
                        <p className="text-sm text-muted-foreground">
                            Manage user accounts
                        </p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchUsers} disabled={isLoading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>Users</CardTitle>
                            <CardDescription>
                                All registered users in the system
                            </CardDescription>
                        </div>
                        <div className="relative w-64">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search users..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-8"
                            />
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    <DataTable
                        columns={columns}
                        data={users}
                        total={totalUsers}
                        page={page}
                        pageSize={pageSize}
                        loading={isLoading}
                        onPageChange={setPage}
                        rowKey={(user) => user.id}
                        emptyMessage={searchQuery ? 'No users found matching your search' : 'No users found'}
                        itemName="users"
                        actions={(user) => (
                            user.id !== currentUserId ? (
                                <div className="flex justify-end">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-destructive hover:text-destructive"
                                        onClick={() => setDeleteUserId(user.id)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ) : null
                        )}
                    />
                </CardContent>
            </Card>

            {/* Delete User Confirmation Dialog */}
            <Dialog open={!!deleteUserId} onOpenChange={() => setDeleteUserId(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete User</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete this user? This action cannot be undone.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteUserId(null)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleDeleteUser}
                            disabled={isDeleting}
                        >
                            {isDeleting ? 'Deleting...' : 'Delete User'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

        </div>
    )
}
