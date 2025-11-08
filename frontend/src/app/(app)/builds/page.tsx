'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { Search, Filter, ExternalLink, Loader2, Info, Sparkles, X } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { buildApi, riskApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { BuildDetail, RiskExplanation } from '@/types'

const riskOrder = ['critical', 'high', 'medium', 'low'] as const

const STATUS_LABELS: Record<string, string> = {
  queued: 'Đang chờ',
  in_progress: 'Đang chạy',
  completed: 'Hoàn thành',
}

const CONCLUSION_LABELS: Record<string, string> = {
  success: 'Thành công',
  failure: 'Thất bại',
  neutral: 'Trung tính',
  cancelled: 'Đã hủy',
}

export default function BuildsPage() {
  const [builds, setBuilds] = useState<BuildDetail[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [riskFilter, setRiskFilter] = useState<(typeof riskOrder)[number] | 'all'>('all')
  const [repoFilter, setRepoFilter] = useState<'all' | string>('all')
  const [branchFilter, setBranchFilter] = useState<'all' | string>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedBuild, setSelectedBuild] = useState<BuildDetail | null>(null)
  const [riskInsight, setRiskInsight] = useState<RiskExplanation | null>(null)
  const [insightLoading, setInsightLoading] = useState(false)
  const [insightError, setInsightError] = useState<string | null>(null)

  useEffect(() => {
    const fetchBuilds = async () => {
      try {
        const response = await buildApi.getAll({ limit: 200 })
        setBuilds(response.builds)
      } catch (err) {
        console.error(err)
        setError('Không thể tải danh sách builds. Kiểm tra backend API.')
      } finally {
        setLoading(false)
      }
    }

    fetchBuilds()
  }, [])

  const handleSelectBuild = async (build: BuildDetail) => {
    setSelectedBuild(build)
    setRiskInsight(null)
    setInsightError(null)
    setInsightLoading(true)
    try {
      const data = await riskApi.getRiskExplanation(build.id)
      setRiskInsight(data)
    } catch (err) {
      console.error(err)
      setInsightError('Không thể tải giải thích rủi ro cho build này.')
    } finally {
      setInsightLoading(false)
    }
  }

  const handleCloseInsight = () => {
    setSelectedBuild(null)
    setRiskInsight(null)
    setInsightError(null)
  }

  const repositories = useMemo(
    () => Array.from(new Set(builds.map((build) => build.repository))).sort(),
    [builds],
  )

  const branches = useMemo(
    () => Array.from(new Set(builds.map((build) => build.branch))).sort(),
    [builds],
  )

  const filteredBuilds = useMemo(() => {
    return builds.filter((build) => {
      const matchesSearch =
        build.repository.toLowerCase().includes(searchTerm.toLowerCase()) ||
        build.branch.toLowerCase().includes(searchTerm.toLowerCase()) ||
        build.commit_sha.toLowerCase().includes(searchTerm.toLowerCase())

      const matchesRepo = repoFilter === 'all' || build.repository === repoFilter
      const matchesBranch = branchFilter === 'all' || build.branch === branchFilter
      const matchesRisk =
        riskFilter === 'all' ||
        build.risk_assessment?.risk_level === riskFilter ||
        (riskFilter === 'low' && !build.risk_assessment)

      return matchesSearch && matchesRisk && matchesRepo && matchesBranch
    })
  }, [branchFilter, builds, repoFilter, riskFilter, searchTerm])

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Đang tải danh sách builds...</CardTitle>
            <CardDescription>Kết nối tới backend để lấy dữ liệu workflow runs.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Vui lòng chờ trong giây lát.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-md border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-900/20">
          <CardHeader>
            <CardTitle className="text-red-600 dark:text-red-300">Không thể tải dữ liệu</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Đảm bảo service FastAPI đang chạy tại <code>{process.env.NEXT_PUBLIC_API_URL}</code>.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Danh sách builds</CardTitle>
            <CardDescription>
              Giám sát các workflow runs đã đồng bộ từ GitHub Actions thông qua BuildGuard collector.
            </CardDescription>
          </div>
          <div className="flex w-full flex-col gap-3">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <div className="relative flex-1 md:col-span-2 xl:col-span-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Tìm theo repository, branch, commit..."
                  className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-slate-800 dark:bg-slate-900"
                />
              </div>
              <div>
                <select
                  value={repoFilter}
                  onChange={(event) => setRepoFilter(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none dark:border-slate-800 dark:bg-slate-900"
                >
                  <option value="all">Tất cả repositories</option>
                  {repositories.map((repo) => (
                    <option key={repo} value={repo}>
                      {repo}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <select
                  value={branchFilter}
                  onChange={(event) => setBranchFilter(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none dark:border-slate-800 dark:bg-slate-900"
                >
                  <option value="all">Tất cả branches</option>
                  {branches.map((branch) => (
                    <option key={branch} value={branch}>
                      {branch}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <div className="flex gap-2">
                <FilterButton label="Tất cả" active={riskFilter === 'all'} onClick={() => setRiskFilter('all')} />
                {riskOrder.map((level) => (
                  <FilterButton
                    key={level}
                    label={level}
                    active={riskFilter === level}
                    onClick={() => setRiskFilter(level)}
                    intent={level}
                  />
                ))}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Build
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Repository · Workflow
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Risk
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Status
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Thời gian
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {filteredBuilds.map((build) => (
                <tr key={build.id} className="hover:bg-blue-50/40">
                  <td className="px-4 py-3">
                    <div className="flex flex-col">
                      <span className="font-semibold text-slate-800">#{build.build_number}</span>
                      <span className="text-xs text-muted-foreground">{build.commit_sha}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col">
                      <span className="font-medium">{build.repository}</span>
                      <span className="text-xs text-muted-foreground">
                        {build.workflow_name} · {build.branch}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleSelectBuild(build)}
                      className="flex w-full flex-col items-start gap-1 rounded-lg border border-transparent px-1 py-1 text-left transition hover:border-blue-200 hover:bg-blue-50/40"
                    >
                      <RiskBadge level={build.risk_assessment?.risk_level ?? 'low'}>
                        {build.risk_assessment?.risk_score?.toFixed(2) ?? '0.00'}
                      </RiskBadge>
                      <span className="text-xs text-muted-foreground">
                        Uncertainty: {build.risk_assessment?.uncertainty?.toFixed(2) ?? '0.00'}
                      </span>
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600">
                        <Sparkles className="h-3 w-3" />
                        Xem giải thích
                      </span>
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      status={build.status}
                      conclusion={build.conclusion}
                      showConclusion={build.status === 'completed'}
                    />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {build.started_at ? new Date(build.started_at).toLocaleString('vi-VN') : 'N/A'}
                    <br />
                    {build.duration_seconds ? `${Math.round(build.duration_seconds / 60)} phút` : 'Đang chạy'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/builds/${build.id}`}
                        className="rounded-lg border border-blue-200 px-3 py-1 text-xs font-semibold text-blue-600 transition hover:bg-blue-600 hover:text-white"
                      >
                        Chi tiết
                      </Link>
                      <a
                        href={build.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1 text-xs text-muted-foreground transition hover:border-blue-500 hover:text-blue-600"
                      >
                        Logs
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredBuilds.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-sm text-muted-foreground">
                    Không tìm thấy build nào khớp với bộ lọc hiện tại.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
      {selectedBuild ? (
        <RiskInsightPanel
          build={selectedBuild}
          explanation={riskInsight}
          loading={insightLoading}
          error={insightError}
          onClose={handleCloseInsight}
        />
      ) : null}
    </div>
  )
}

interface RiskInsightPanelProps {
  build: BuildDetail
  explanation: RiskExplanation | null
  loading: boolean
  error: string | null
  onClose: () => void
}

function RiskInsightPanel({ build, explanation, loading, error, onClose }: RiskInsightPanelProps) {
  return (
    <Card className="border border-blue-200 bg-blue-50/60 dark:border-blue-900/60 dark:bg-blue-950/30">
      <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle className="text-base">Giải thích rủi ro · {build.repository}</CardTitle>
          <CardDescription>
            Workflow {build.workflow_name} · Branch {build.branch} · Build #{build.build_number}
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center rounded-full border border-blue-200 px-3 py-1 text-xs font-semibold text-blue-700 dark:border-blue-800 dark:text-blue-200">
            Risk level: {build.risk_assessment?.risk_level ?? 'low'}
          </span>
          {explanation ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-white px-3 py-1 text-xs font-semibold text-emerald-600 dark:bg-slate-900">
              <Info className="h-3.5 w-3.5" />
              Độ tin cậy: {explanation.confidence}
            </span>
          ) : null}
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-200 p-2 text-muted-foreground transition hover:bg-red-50 hover:text-red-600 dark:border-slate-700 dark:hover:bg-red-900/30 dark:hover:text-red-300"
            aria-label="Đóng giải thích rủi ro"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Đang tải giải thích từ API Bayesian risk engine...
          </div>
        ) : error ? (
          <p className="text-sm text-red-600 dark:text-red-300">{error}</p>
        ) : explanation ? (
          <>
            <div className="rounded-xl border border-blue-200 bg-white/70 p-4 text-sm text-slate-700 dark:border-blue-900 dark:bg-slate-900/60 dark:text-slate-200">
              <p className="font-semibold flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-blue-600" />
                {explanation.summary}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Mô hình {explanation.model_version ?? 'mock-0.1.0'} · cập nhật{' '}
                {new Date(explanation.updated_at).toLocaleString('vi-VN')}
              </p>
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase text-muted-foreground">Đóng góp của các yếu tố</p>
                <div className="mt-3 space-y-3">
                  {explanation.drivers.map((driver) => (
                    <div key={driver.key} className="rounded-lg border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-700 dark:text-slate-100">{driver.label}</span>
                        <span className="text-muted-foreground">{Math.round(driver.contribution * 100)}%</span>
                      </div>
                      <div className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                        <div
                          className={cn(
                            'h-2 rounded-full transition-all',
                            driver.impact === 'increase' ? 'bg-red-500' : 'bg-emerald-500',
                          )}
                          style={{ width: `${Math.min(100, driver.contribution * 100)}%` }}
                        />
                      </div>
                      <p className="mt-2 text-muted-foreground">{driver.description}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(driver.metrics).map(([key, value]) => (
                          <span
                            key={`${driver.key}-${key}`}
                            className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200"
                          >
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-4">
                <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
                  <p className="font-semibold text-slate-700 dark:text-slate-100">Đóng góp theo nhóm dữ liệu</p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {Object.entries(explanation.feature_breakdown).map(([name, value]) => (
                      <div
                        key={name}
                        className="rounded-lg border border-slate-100 bg-slate-50 p-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
                      >
                        <p className="font-semibold">{name}</p>
                        <p className="text-lg font-bold">{value.toFixed(1)}%</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
                  <p className="font-semibold text-slate-700 dark:text-slate-100">Hành động khuyến nghị</p>
                  <ul className="mt-2 space-y-2 text-muted-foreground">
                    {explanation.recommended_actions.map((action) => (
                      <li key={action} className="flex items-start gap-2">
                        <Sparkles className="h-3.5 w-3.5 text-blue-500" />
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Chọn một build để xem giải thích chi tiết.</p>
        )}
      </CardContent>
    </Card>
  )
}

interface FilterButtonProps {
  label: string
  active: boolean
  onClick: () => void
  intent?: (typeof riskOrder)[number]
}

function FilterButton({ label, active, onClick, intent }: FilterButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full border px-3 py-1 text-xs font-semibold capitalize transition',
        active ? 'border-transparent text-white shadow-sm' : 'border-slate-200 text-slate-600 hover:border-blue-500 hover:text-blue-600 dark:border-slate-700',
        intent === 'low' && active && 'bg-emerald-500',
        intent === 'medium' && active && 'bg-amber-500',
        intent === 'high' && active && 'bg-orange-500',
        intent === 'critical' && active && 'bg-red-500',
        !intent && active && 'bg-blue-600',
      )}
    >
      {label}
    </button>
  )
}

interface RiskBadgeProps {
  level: string
  children: React.ReactNode
}

function RiskBadge({ level, children }: RiskBadgeProps) {
  return (
    <span
      className={cn(
        'mb-1 inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase',
        level === 'low' && 'bg-emerald-100 text-emerald-700',
        level === 'medium' && 'bg-amber-100 text-amber-700',
        level === 'high' && 'bg-orange-100 text-orange-700',
        level === 'critical' && 'bg-red-100 text-red-700',
      )}
    >
      {level}
      <span className="font-mono text-sm">{children}</span>
    </span>
  )
}

interface StatusBadgeProps {
  status: string
  conclusion?: string
  showConclusion?: boolean
}

function StatusBadge({ status, conclusion, showConclusion }: StatusBadgeProps) {
  const statusLabel = STATUS_LABELS[status] ?? status
  const conclusionLabel =
    conclusion && showConclusion
      ? CONCLUSION_LABELS[conclusion] ?? conclusion
      : undefined

  return (
    <div className="flex flex-col gap-1">
      <span className="inline-flex items-center rounded-full border border-blue-200 px-2 py-0.5 text-xs font-semibold text-blue-600">
        {statusLabel}
      </span>
      {conclusionLabel ? (
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold',
            conclusion === 'success' && 'border-emerald-200 text-emerald-600',
            conclusion === 'failure' && 'border-red-200 text-red-600',
            conclusion === 'neutral' && 'border-slate-200 text-slate-600',
            conclusion === 'cancelled' && 'border-amber-200 text-amber-600',
          )}
        >
          {conclusionLabel}
        </span>
      ) : null}
    </div>
  )
}
