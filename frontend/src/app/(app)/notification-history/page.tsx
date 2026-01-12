'use client';

import { ArrowLeft } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { NotificationsList } from '@/components/notifications/NotificationsList';

export default function NotificationHistoryPage() {
    const router = useRouter();

    return (
        <div className="container mx-auto py-8 px-4 max-w-4xl">
            <div className="mb-8 flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => router.back()}>
                    <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                    <h1 className="text-3xl font-bold">Notification History</h1>
                    <p className="text-muted-foreground mt-2">
                        View your past notifications and alerts.
                    </p>
                </div>
            </div>

            <div className="space-y-6">
                <NotificationsList />
            </div>
        </div>
    );
}
