'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Bell, Loader2, User } from 'lucide-react';
import { useSearchParams, useRouter } from 'next/navigation';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { userSettingsApi, UpdateUserSettingsRequest } from '@/lib/api';
import { NotificationsList } from '@/components/notifications/NotificationsList';
import { ProfileSettings } from '@/components/settings/ProfileSettings';
import { useDebounce } from '@/hooks/use-debounce';

interface SettingsState {
    browserNotifications: boolean;
    savedBrowserNotifications: boolean;
    isLoading: boolean;
    isSaving: boolean;
}

export default function SettingsPage() {
    const { toast } = useToast();
    const searchParams = useSearchParams();
    const router = useRouter();
    const saveRequestIdRef = useRef(0);

    const [activeTab, setActiveTab] = useState('notifications');

    const [settingsState, setSettingsState] = useState<SettingsState>({
        browserNotifications: true,
        savedBrowserNotifications: true,
        isLoading: true,
        isSaving: false,
    });

    const debouncedBrowserNotifications = useDebounce(settingsState.browserNotifications, 500);

    // Sync tab with URL
    useEffect(() => {
        const tab = searchParams.get('tab');
        if (tab && ['notifications', 'profile'].includes(tab)) {
            setActiveTab(tab);
        }
    }, [searchParams]);

    const handleTabChange = (value: string) => {
        setActiveTab(value);
        const params = new URLSearchParams(searchParams.toString());
        params.set('tab', value);
        router.push(`/settings?${params.toString()}`);
    };

    // Load user settings on mount
    const loadSettings = useCallback(async () => {
        try {
            const userSettingsResponse = await userSettingsApi.get();
            setSettingsState({
                browserNotifications: userSettingsResponse.browser_notifications,
                savedBrowserNotifications: userSettingsResponse.browser_notifications,
                isLoading: false,
                isSaving: false,
            });
        } catch {
            // Use defaults if API fails
            setSettingsState((currentSettingsState) => ({
                ...currentSettingsState,
                savedBrowserNotifications: currentSettingsState.browserNotifications,
                isLoading: false,
            }));
        }
    }, []);

    useEffect(() => {
        loadSettings();
    }, [loadSettings]);

    const persistBrowserNotifications = useCallback(
        async (browserNotificationsEnabled: boolean) => {
            const saveRequestId = saveRequestIdRef.current + 1;
            saveRequestIdRef.current = saveRequestId;

            setSettingsState((currentSettingsState) => ({
                ...currentSettingsState,
                isSaving: true,
            }));

            try {
                const updateRequest: UpdateUserSettingsRequest = {
                    browser_notifications: browserNotificationsEnabled,
                };
                const updatedSettingsResponse = await userSettingsApi.update(updateRequest);

                if (saveRequestId !== saveRequestIdRef.current) {
                    return;
                }

                setSettingsState((currentSettingsState) => ({
                    ...currentSettingsState,
                    browserNotifications: updatedSettingsResponse.browser_notifications,
                    savedBrowserNotifications: updatedSettingsResponse.browser_notifications,
                    isSaving: false,
                }));
            } catch {
                if (saveRequestId !== saveRequestIdRef.current) {
                    return;
                }

                toast({
                    title: 'Error saving settings',
                    description: 'Please try again later.',
                    variant: 'destructive',
                });

                setSettingsState((currentSettingsState) => ({
                    ...currentSettingsState,
                    browserNotifications: currentSettingsState.savedBrowserNotifications,
                    isSaving: false,
                }));
            }
        },
        [toast]
    );

    useEffect(() => {
        if (settingsState.isLoading) {
            return;
        }

        if (debouncedBrowserNotifications === settingsState.savedBrowserNotifications) {
            return;
        }

        void persistBrowserNotifications(debouncedBrowserNotifications);
    }, [
        debouncedBrowserNotifications,
        persistBrowserNotifications,
        settingsState.isLoading,
        settingsState.savedBrowserNotifications,
    ]);

    if (settingsState.isLoading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    <span>Loading settings…</span>
                </div>
            </div>
        );
    }

    return (
        <div className="container mx-auto py-8 px-4 max-w-4xl">
            <div className="mb-8">
                <h1 className="text-3xl font-bold">Settings</h1>
                <p className="text-muted-foreground mt-2">
                    Manage your notification preferences and view your profile.
                </p>
            </div>

            <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
                <TabsList className="grid w-full grid-cols-2 max-w-md">
                    <TabsTrigger value="notifications" className="flex items-center gap-2">
                        <Bell className="h-4 w-4" />
                        Notifications
                    </TabsTrigger>
                    <TabsTrigger value="profile" className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        Profile
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
                                        Personal Notification Settings
                                    </CardTitle>
                                    <CardDescription>
                                        Control whether this browser should receive in-app alerts.
                                    </CardDescription>
                                </div>
                                <Badge
                                    variant="outline"
                                    className={
                                        settingsState.browserNotifications
                                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                            : 'border-slate-200 bg-slate-50 text-slate-600'
                                    }
                                >
                                    {settingsState.browserNotifications ? 'Enabled' : 'Paused'}
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-start justify-between gap-4">
                                <div className="space-y-1">
                                    <Label htmlFor="browser-notifications">
                                        Enable Browser Notifications
                                    </Label>
                                    <p className="text-sm text-muted-foreground">
                                        {settingsState.browserNotifications
                                            ? 'You will receive alerts in this browser.'
                                            : 'Notifications are paused in this browser.'}
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                        {settingsState.isSaving
                                            ? 'Saving your preference...'
                                            : settingsState.browserNotifications !==
                                                settingsState.savedBrowserNotifications
                                            ? 'Saving soon...'
                                            : 'Saved.'}
                                    </p>
                                </div>
                                <Switch
                                    id="browser-notifications"
                                    checked={settingsState.browserNotifications}
                                    onCheckedChange={(checked) =>
                                        setSettingsState((currentSettingsState) => ({
                                            ...currentSettingsState,
                                            browserNotifications: checked,
                                        }))
                                    }
                                />
                            </div>
                        </CardContent>
                    </Card>

                    {/* Notification History */}
                    <NotificationsList />
                </TabsContent>

                <TabsContent value="profile" className="space-y-6">
                    <ProfileSettings />
                </TabsContent>
            </Tabs>
        </div>
    );
}
