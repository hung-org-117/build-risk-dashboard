'use client'

import { useState, useEffect } from 'react'
import { Save, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { settingsApi, usersApi } from '@/lib/api'
import type { ApplicationSettings, UserAccount } from '@/types'

export function NotificationsTab() {
  const [settings, setSettings] = useState<ApplicationSettings | null>(null)
  const [user, setUser] = useState<UserAccount | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const [settingsData, userData] = await Promise.all([
        settingsApi.get(),
        usersApi.getCurrentUser(),
      ])
      setSettings(settingsData)
      setUser(userData)
    } catch (error) {
      toast({ title: 'Failed to load settings', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!settings) return

    setSaving(true)
    try {
      await Promise.all([
        settingsApi.update(settings),
        usersApi.updateCurrentUser({
          notification_email: user?.notification_email || null,
        }),
      ])
      toast({ title: 'Notification settings saved successfully' })
    } catch (error) {
      toast({ title: 'Failed to save settings', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!settings) return null

  return (
    <div className="space-y-6">
      {/* Personal Email Settings */}
      {user && (
        <Card>
          <CardHeader>
            <CardTitle>My Notification Settings</CardTitle>
            <CardDescription>
              Configure how you receive personal notifications.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Label htmlFor="personal-email">Notification Email</Label>
              <Input
                id="personal-email"
                value={user.notification_email || ''}
                onChange={(e) =>
                  setUser({
                    ...user,
                    notification_email: e.target.value,
                  })
                }
                placeholder={user.email}
              />
              <p className="text-sm text-muted-foreground">
                Leave empty to use your default email address ({user.email}).
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Email */}
      <Card>
        <CardHeader>
          <CardTitle>Email Notifications</CardTitle>
          <CardDescription>Send notifications via email</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="email-enabled">Enable Email Notifications</Label>
            <Switch
              id="email-enabled"
              checked={settings.notifications.email_enabled}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  notifications: { ...settings.notifications, email_enabled: checked },
                })
              }
            />
          </div>
          {settings.notifications.email_enabled && (
            <div className="space-y-2">
              <Label htmlFor="email-recipients">Recipients (comma-separated)</Label>
              <Input
                id="email-recipients"
                value={settings.notifications.email_recipients}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    notifications: { ...settings.notifications, email_recipients: e.target.value },
                  })
                }
                placeholder="user@example.com, admin@example.com"
              />
            </div>
          )}
        </CardContent>
      </Card>
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Save Changes
        </Button>
      </div>
    </div>
  )
}
