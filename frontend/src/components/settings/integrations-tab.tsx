'use client'

import { useState, useEffect } from 'react'
import { Save, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { settingsApi } from '@/lib/api'
import type { ApplicationSettings } from '@/types'

export function IntegrationsTab() {
  const [settings, setSettings] = useState<ApplicationSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const data = await settingsApi.get()
      setSettings(data)
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
      await settingsApi.update(settings)
      toast({ title: 'Settings saved successfully' })
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
      {/* SonarQube */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">SonarQube</CardTitle>
          <CardDescription>Code quality and security analysis</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="sonar-enabled">Enable SonarQube</Label>
            <Switch
              id="sonar-enabled"
              checked={settings.sonarqube.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, sonarqube: { ...settings.sonarqube, enabled: checked } })
              }
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="sonar-url">Host URL</Label>
              <Input
                id="sonar-url"
                value={settings.sonarqube.host_url}
                onChange={(e) =>
                  setSettings({ ...settings, sonarqube: { ...settings.sonarqube, host_url: e.target.value } })
                }
                placeholder="http://localhost:9000"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sonar-project-key">Default Project Key</Label>
              <Input
                id="sonar-project-key"
                value={settings.sonarqube.default_project_key || ''}
                onChange={(e) =>
                  setSettings({ ...settings, sonarqube: { ...settings.sonarqube, default_project_key: e.target.value } })
                }
                placeholder="build-risk-ui"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="sonar-token">Authentication Token</Label>
            <Input
              id="sonar-token"
              type="password"
              value={settings.sonarqube.token || ''}
              onChange={(e) =>
                setSettings({ ...settings, sonarqube: { ...settings.sonarqube, token: e.target.value } })
              }
              placeholder="Enter token to update"
            />
          </div>
        </CardContent>
      </Card>

      {/* CircleCI */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">CircleCI</CardTitle>
          <CardDescription>CircleCI integration for build data</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="circleci-enabled">Enable CircleCI</Label>
            <Switch
              id="circleci-enabled"
              checked={settings.circleci.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, circleci: { ...settings.circleci, enabled: checked } })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="circleci-url">API Base URL</Label>
            <Input
              id="circleci-url"
              value={settings.circleci.base_url || ''}
              onChange={(e) =>
                setSettings({ ...settings, circleci: { ...settings.circleci, base_url: e.target.value } })
              }
              placeholder="https://circleci.com/api/v2"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="circleci-token">API Token</Label>
            <Input
              id="circleci-token"
              type="password"
              value={settings.circleci.token || ''}
              onChange={(e) =>
                setSettings({ ...settings, circleci: { ...settings.circleci, token: e.target.value } })
              }
              placeholder="Enter token to update"
            />
          </div>
        </CardContent>
      </Card>

      {/* Travis CI */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Travis CI</CardTitle>
          <CardDescription>Travis CI integration for build data</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="travis-enabled">Enable Travis CI</Label>
            <Switch
              id="travis-enabled"
              checked={settings.travis.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, travis: { ...settings.travis, enabled: checked } })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="travis-url">API Base URL</Label>
            <Input
              id="travis-url"
              value={settings.travis.base_url || ''}
              onChange={(e) =>
                setSettings({ ...settings, travis: { ...settings.travis, base_url: e.target.value } })
              }
              placeholder="https://api.travis-ci.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="travis-token">API Token</Label>
            <Input
              id="travis-token"
              type="password"
              value={settings.travis.token || ''}
              onChange={(e) =>
                setSettings({ ...settings, travis: { ...settings.travis, token: e.target.value } })
              }
              placeholder="Enter token to update"
            />
          </div>
        </CardContent>
      </Card>

      {/* Trivy Security Scanner */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Trivy Security Scanner</CardTitle>
          <CardDescription>Container and dependency security scanning</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="trivy-enabled">Enable Trivy</Label>
            <Switch
              id="trivy-enabled"
              checked={settings.trivy.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, trivy: { ...settings.trivy, enabled: checked } })
              }
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="trivy-severity">Severity Levels</Label>
              <Input
                id="trivy-severity"
                value={settings.trivy.severity}
                onChange={(e) =>
                  setSettings({ ...settings, trivy: { ...settings.trivy, severity: e.target.value } })
                }
                placeholder="CRITICAL,HIGH,MEDIUM"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="trivy-timeout">Timeout (seconds)</Label>
              <Input
                id="trivy-timeout"
                type="number"
                value={settings.trivy.timeout || 300}
                onChange={(e) =>
                  setSettings({ ...settings, trivy: { ...settings.trivy, timeout: parseInt(e.target.value) || 300 } })
                }
                placeholder="300"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="trivy-skip-dirs">Skip Directories</Label>
            <Input
              id="trivy-skip-dirs"
              value={settings.trivy.skip_dirs || ''}
              onChange={(e) =>
                setSettings({ ...settings, trivy: { ...settings.trivy, skip_dirs: e.target.value } })
              }
              placeholder="node_modules,vendor,.git"
            />
            <p className="text-xs text-muted-foreground">Comma-separated list of directories to skip during scanning</p>
          </div>
        </CardContent>
      </Card>

      {/* Save Button - Fixed at bottom */}
      <div className="sticky bottom-4 flex justify-end">
        <Button onClick={handleSave} disabled={saving} size="lg">
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Save Changes
        </Button>
      </div>
    </div>
  )
}
