'use client';

import { useState, useEffect, useCallback } from 'react';
import { Bell, Loader2, User, Mail, AlertTriangle, History, Save } from 'lucide-react';
import { useSearchParams, useRouter } from 'next/navigation';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { usersApi } from '@/lib/api';
import { NotificationsList } from '@/components/notifications/NotificationsList';
import { ProfileSettings } from '@/components/settings/ProfileSettings';
import type { NotificationSubscription, UserAccount } from '@/types';

// User-facing notification types with metadata
const USER_NOTIFICATION_TYPES = [
    {
        key: 'high_risk_detected',
        label: 'High Risk Build Detected',
        description: 'When a build is predicted as HIGH risk',
        isCritical: true,
    },
    {
        key: 'build_prediction_ready',
        label: 'Build Predictions Ready',
        description: 'When predictions are complete for your repositories',
        isCritical: false,
    },
];

// Admin-only notification types
const ADMIN_NOTIFICATION_TYPES = [
    {
        category: 'Model Pipeline',
        description: 'Feature extraction and prediction notifications',
        events: [
            {
                key: 'pipeline_completed',
                label: 'Pipeline Completed',
                description: 'When feature extraction completes successfully',
                isCritical: false,
            },
            {
                key: 'pipeline_failed',
                label: 'Pipeline Failed',
                description: 'When feature extraction pipeline fails',
                isCritical: true,
            },
        ],
    },
    {
        category: 'Dataset Enrichment',
        description: 'Dataset enrichment notifications',
        events: [
            {
                key: 'dataset_enrichment_completed',
                label: 'Enrichment Completed',
                description: 'When dataset enrichment process completes',
                isCritical: false,
            },
            {
                key: 'dataset_enrichment_failed',
                label: 'Enrichment Failed',
                description: 'When dataset enrichment process fails',
                isCritical: true,
            },
        ],
    },
    {
        category: 'System',
        description: 'System and rate limit notifications',
        events: [
            {
                key: 'rate_limit_exhausted',
                label: 'Rate Limit Exhausted',
                description: 'When all GitHub tokens are rate limited',
                isCritical: true,
            },
            {
                key: 'system_alerts',
                label: 'System Alerts',
                description: 'Important system notifications',
                isCritical: true,
            },
        ],
    },
];

export default function SettingsPage() {
    const { toast } = useToast();
    const searchParams = useSearchParams();
    const router = useRouter();

    const [activeTab, setActiveTab] = useState('notifications');
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [user, setUser] = useState<UserAccount | null>(null);
    const [originalUser, setOriginalUser] = useState<UserAccount | null>(null);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

    // Sync tab with URL
    useEffect(() => {
        const tab = searchParams.get('tab');
        if (tab && ['notifications', 'profile', 'history'].includes(tab)) {
            setActiveTab(tab);
        }
    }, [searchParams]);

    const handleTabChange = (value: string) => {
        setActiveTab(value);
        const params = new URLSearchParams(searchParams.toString());
        params.set('tab', value);
        router.push(`/settings?${params.toString()}`);
    };

    // Load user on mount
    useEffect(() => {
        const loadUser = async () => {
            try {
                const userData = await usersApi.getCurrentUser();
                setUser(userData);
                setOriginalUser(userData);
            } catch {
                toast({
                    title: 'Error loading settings',
                    variant: 'destructive',
                });
            } finally {
                setIsLoading(false);
            }
        };
        loadUser();
    }, [toast]);

    // Check for unsaved changes
    useEffect(() => {
        if (!user || !originalUser) {
            setHasUnsavedChanges(false);
            return;
        }
        const hasChanges =
            user.browser_notifications !== originalUser.browser_notifications ||
            user.email_notifications_enabled !== originalUser.email_notifications_enabled ||
            user.notification_email !== originalUser.notification_email ||
            JSON.stringify(user.subscriptions) !== JSON.stringify(originalUser.subscriptions);
        setHasUnsavedChanges(hasChanges);
    }, [user, originalUser]);

    // Save function
    const handleSave = useCallback(async () => {
        if (!user) return;

        setIsSaving(true);
        try {
            const updatedUser = await usersApi.updateCurrentUser({
                browser_notifications: user.browser_notifications,
                email_notifications_enabled: user.email_notifications_enabled,
                notification_email: user.notification_email,
                subscriptions: user.subscriptions,
            });
            setUser(updatedUser);
            setOriginalUser(updatedUser);
            setHasUnsavedChanges(false);
            toast({
                title: 'Settings saved',
                description: 'Your notification preferences have been updated.',
            });
        } catch {
            toast({
                title: 'Error saving settings',
                variant: 'destructive',
            });
        } finally {
            setIsSaving(false);
        }
    }, [user, toast]);

    const handleBrowserNotificationsChange = (checked: boolean) => {
        if (!user) return;
        setUser({ ...user, browser_notifications: checked });
    };

    const handleEmailNotificationsChange = (checked: boolean) => {
        if (!user) return;
        setUser({ ...user, email_notifications_enabled: checked });
    };

    const handleEmailChange = (email: string) => {
        if (!user) return;
        setUser({ ...user, notification_email: email || null });
    };

    const handleSubscriptionChange = (
        eventType: string,
        channel: 'in_app' | 'email',
        checked: boolean
    ) => {
        if (!user) return;
        const currentSub = user.subscriptions[eventType] || { in_app: true, email: false };
        const newSubscriptions: Record<string, NotificationSubscription> = {
            ...user.subscriptions,
            [eventType]: {
                ...currentSub,
                [channel]: checked,
            },
        };
        setUser({ ...user, subscriptions: newSubscriptions });
    };

    const handleDiscardChanges = () => {
        if (originalUser) {
            setUser(originalUser);
            setHasUnsavedChanges(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    <span>Loading settings…</span>
                </div>
            </div>
        );
    }

    if (!user) return null;

    return (
        <div className="container mx-auto py-8 px-4 max-w-4xl">
            <div className="mb-8">
                <h1 className="text-3xl font-bold">Settings</h1>
                <p className="text-muted-foreground mt-2">
                    Manage your notification preferences and view your profile.
                </p>
            </div>

            <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
                <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="notifications" className="flex items-center gap-2">
                        <Bell className="h-4 w-4" />
                        Notifications
                    </TabsTrigger>
                    <TabsTrigger value="profile" className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        Profile
                    </TabsTrigger>
                    <TabsTrigger value="history" className="flex items-center gap-2">
                        <History className="h-4 w-4" />
                        History
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="notifications" className="space-y-6">
                    {/* Browser Notifications */}
                    <Card>
                        <CardHeader>
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="space-y-1">
                                    <CardTitle className="flex items-center gap-2">
                                        <Bell className="h-5 w-5" />
                                        Browser Notifications
                                    </CardTitle>
                                    <CardDescription>
                                        Receive in-app alerts in this browser.
                                    </CardDescription>
                                </div>
                                <Badge
                                    variant="outline"
                                    className={
                                        user.browser_notifications
                                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                            : 'border-slate-200 bg-slate-50 text-slate-600'
                                    }
                                >
                                    {user.browser_notifications ? 'Enabled' : 'Paused'}
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center justify-between">
                                <Label htmlFor="browser-notifications">
                                    Enable Browser Notifications
                                </Label>
                                <Switch
                                    id="browser-notifications"
                                    checked={user.browser_notifications}
                                    onCheckedChange={handleBrowserNotificationsChange}
                                />
                            </div>
                        </CardContent>
                    </Card>

                    {/* Email Notifications */}
                    <Card>
                        <CardHeader>
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="space-y-1">
                                    <CardTitle className="flex items-center gap-2">
                                        <Mail className="h-5 w-5" />
                                        Email Notifications
                                    </CardTitle>
                                    <CardDescription>
                                        Receive important alerts via email.
                                    </CardDescription>
                                </div>
                                <Badge
                                    variant="outline"
                                    className={
                                        user.email_notifications_enabled
                                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                            : 'border-slate-200 bg-slate-50 text-slate-600'
                                    }
                                >
                                    {user.email_notifications_enabled ? 'Enabled' : 'Disabled'}
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="email-notifications">
                                    Enable Email Notifications
                                </Label>
                                <Switch
                                    id="email-notifications"
                                    checked={user.email_notifications_enabled}
                                    onCheckedChange={handleEmailNotificationsChange}
                                />
                            </div>
                            {user.email_notifications_enabled && (
                                <div className="space-y-2">
                                    <Label htmlFor="notification-email">Notification Email</Label>
                                    <Input
                                        id="notification-email"
                                        type="email"
                                        placeholder={user.email}
                                        value={user.notification_email || ''}
                                        onChange={(e) => handleEmailChange(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Leave empty to use your account email ({user.email})
                                    </p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Event Subscriptions */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Event Subscriptions</CardTitle>
                            <CardDescription>
                                Choose which events you want to be notified about.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                {/* Header */}
                                <div className="grid grid-cols-[1fr,80px,80px] gap-2 text-xs font-medium text-muted-foreground border-b pb-2">
                                    <div>Event</div>
                                    <div className="text-center">In-App</div>
                                    <div className="text-center">Email</div>
                                </div>
                                {/* Event rows */}
                                {USER_NOTIFICATION_TYPES.map((event) => {
                                    const sub = user.subscriptions[event.key] || { in_app: true, email: false };
                                    return (
                                        <div
                                            key={event.key}
                                            className="grid grid-cols-[1fr,80px,80px] gap-2 items-center py-2"
                                        >
                                            <div className="space-y-0.5">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium text-sm">{event.label}</span>
                                                    {event.isCritical && (
                                                        <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                                                            <AlertTriangle className="h-3 w-3" />
                                                            Critical
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="text-xs text-muted-foreground">
                                                    {event.description}
                                                </p>
                                            </div>
                                            <div className="flex justify-center">
                                                <Switch
                                                    checked={sub.in_app}
                                                    onCheckedChange={(checked) =>
                                                        handleSubscriptionChange(event.key, 'in_app', checked)
                                                    }
                                                />
                                            </div>
                                            <div className="flex justify-center">
                                                <Switch
                                                    checked={sub.email}
                                                    disabled={!user.email_notifications_enabled}
                                                    onCheckedChange={(checked) =>
                                                        handleSubscriptionChange(event.key, 'email', checked)
                                                    }
                                                />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                            {!user.email_notifications_enabled && (
                                <p className="text-xs text-muted-foreground mt-4">
                                    Enable email notifications above to configure email subscriptions.
                                </p>
                            )}
                        </CardContent>
                    </Card>

                    {/* Admin Event Subscriptions - Only visible for admins */}
                    {user.role === 'admin' && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    Admin Notifications
                                    <Badge variant="secondary" className="text-xs">Admin Only</Badge>
                                </CardTitle>
                                <CardDescription>
                                    System and pipeline notifications for administrators.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                {ADMIN_NOTIFICATION_TYPES.map((category) => (
                                    <div key={category.category} className="space-y-3">
                                        <div className="border-b pb-2">
                                            <h4 className="font-semibold text-sm">{category.category}</h4>
                                            <p className="text-xs text-muted-foreground">{category.description}</p>
                                        </div>
                                        <div className="space-y-2">
                                            {/* Header for this category */}
                                            <div className="grid grid-cols-[1fr,80px,80px] gap-2 text-xs font-medium text-muted-foreground">
                                                <div>Event</div>
                                                <div className="text-center">In-App</div>
                                                <div className="text-center">Email</div>
                                            </div>
                                            {/* Event rows */}
                                            {category.events.map((event) => {
                                                const sub = user.subscriptions[event.key] || { in_app: true, email: false };
                                                return (
                                                    <div
                                                        key={event.key}
                                                        className="grid grid-cols-[1fr,80px,80px] gap-2 items-center py-2"
                                                    >
                                                        <div className="space-y-0.5">
                                                            <div className="flex items-center gap-2">
                                                                <span className="font-medium text-sm">{event.label}</span>
                                                                {event.isCritical && (
                                                                    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                                                                        <AlertTriangle className="h-3 w-3" />
                                                                        Critical
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <p className="text-xs text-muted-foreground">
                                                                {event.description}
                                                            </p>
                                                        </div>
                                                        <div className="flex justify-center">
                                                            <Switch
                                                                checked={sub.in_app}
                                                                onCheckedChange={(checked) =>
                                                                    handleSubscriptionChange(event.key, 'in_app', checked)
                                                                }
                                                            />
                                                        </div>
                                                        <div className="flex justify-center">
                                                            <Switch
                                                                checked={sub.email}
                                                                disabled={!user.email_notifications_enabled}
                                                                onCheckedChange={(checked) =>
                                                                    handleSubscriptionChange(event.key, 'email', checked)
                                                                }
                                                            />
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    )}

                    {/* Save Button Section */}
                    <div className="flex items-center justify-end gap-3 pt-4">
                        {hasUnsavedChanges && (
                            <span className="text-sm text-amber-600 font-medium">
                                You have unsaved changes
                            </span>
                        )}
                        {hasUnsavedChanges && (
                            <Button
                                variant="outline"
                                onClick={handleDiscardChanges}
                                disabled={isSaving}
                            >
                                Discard
                            </Button>
                        )}
                        <Button
                            onClick={handleSave}
                            disabled={!hasUnsavedChanges || isSaving}
                            className="gap-2"
                        >
                            {isSaving ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Save className="h-4 w-4" />
                            )}
                            {isSaving ? 'Saving...' : 'Save Settings'}
                        </Button>
                    </div>
                </TabsContent>

                <TabsContent value="profile" className="space-y-6">
                    <ProfileSettings />
                </TabsContent>

                <TabsContent value="history" className="space-y-6">
                    <NotificationsList />
                </TabsContent>
            </Tabs>
        </div>
    );
}
