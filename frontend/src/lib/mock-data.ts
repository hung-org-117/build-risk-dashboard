import { addDays, subDays } from 'date-fns'
import type { BuildDetail, Build, RiskAssessment } from '@/types'

type RiskLevel = RiskAssessment['risk_level']

const repositories = [
  {
    name: 'buildguard/core-platform',
    workflows: ['CI', 'Security Scan', 'Release'],
  },
  {
    name: 'buildguard/ui-dashboard',
    workflows: ['CI', 'Chromatic', 'Release'],
  },
  {
    name: 'buildguard/ml-pipeline',
    workflows: ['Model Training', 'Data Sync', 'CI'],
  },
]

const riskPalette: Record<RiskLevel, { score: number; uncertainty: number }> = {
  low: { score: 0.18, uncertainty: 0.05 },
  medium: { score: 0.47, uncertainty: 0.14 },
  high: { score: 0.73, uncertainty: 0.21 },
  critical: { score: 0.9, uncertainty: 0.28 },
}

const riskLevels: RiskLevel[] = ['low', 'medium', 'high', 'critical']
const buildStatuses = ['queued', 'in_progress', 'completed'] as const
const conclusions = ['success', 'failure', 'neutral', 'cancelled'] as const

const authors = [
  { name: 'Lan Pham', email: 'lan.pham@buildguard.dev' },
  { name: 'An Nguyen', email: 'an.nguyen@buildguard.dev' },
  { name: 'Minh Do', email: 'minh.do@buildguard.dev' },
  { name: 'Linh Vu', email: 'linh.vu@buildguard.dev' },
]

const randomItem = <T,>(items: readonly T[]): T => {
  const index = Math.floor(Math.random() * items.length)
  return items[index]
}

const randomNumber = (min: number, max: number, decimals = 0) => {
  const value = Math.random() * (max - min) + min
  return Number(value.toFixed(decimals))
}

const randomDateBetween = (start: Date, end: Date) => {
  const diff = end.getTime() - start.getTime()
  return new Date(start.getTime() + Math.random() * diff)
}

const buildStatusesDisplay: Record<(typeof buildStatuses)[number], string> = {
  queued: 'Đang chờ',
  in_progress: 'Đang chạy',
  completed: 'Hoàn thành',
}

const conclusionDisplay: Record<(typeof conclusions)[number], string> = {
  success: 'Thành công',
  failure: 'Thất bại',
  neutral: 'Trung tính',
  cancelled: 'Đã hủy',
}

export const MOCK_STATUS_LABELS = {
  status: buildStatusesDisplay,
  conclusion: conclusionDisplay,
}

export const generateMockBuild = (id: number): BuildDetail => {
  const repo = randomItem(repositories)
  const author = randomItem(authors)
  const riskLevel = randomItem(riskLevels)
  const status = randomItem(buildStatuses)
  const conclusion = status === 'completed' ? randomItem(conclusions) : undefined

  const startedAt = randomDateBetween(subDays(new Date(), 14), new Date())
  const completedAt =
    status === 'completed' ? addDays(startedAt, 0) : randomDateBetween(startedAt, addDays(startedAt, 1))

  const durationSeconds =
    status === 'completed'
      ? Math.max(120, Math.round((completedAt.getTime() - startedAt.getTime()) / 1000))
      : undefined

  const build: BuildDetail = {
    id,
    repository: repo.name,
    branch: randomItem(['main', 'develop', 'release/v1.6.0', 'feature/feature-x']),
    commit_sha: Math.random().toString(16).slice(2, 9),
    build_number: `#${randomNumber(120, 640, 0)}`,
    workflow_name: randomItem(repo.workflows),
    status,
    conclusion,
    started_at: startedAt.toISOString(),
    completed_at: status === 'completed' ? completedAt.toISOString() : undefined,
    duration_seconds: durationSeconds,
    author_name: author.name,
    author_email: author.email,
    url: 'https://github.com/buildguard/core-platform/actions',
    logs_url: 'https://github.com/buildguard/core-platform/actions/runs/123456789',
    created_at: startedAt.toISOString(),
    updated_at: completedAt?.toISOString(),
    sonarqube_result: {
      id,
      build_id: id,
      bugs: randomNumber(0, 5),
      vulnerabilities: randomNumber(0, 3),
      code_smells: randomNumber(20, 160),
      coverage: randomNumber(40, 85, 1),
      duplicated_lines_density: randomNumber(1, 10, 1),
      technical_debt_minutes: randomNumber(45, 320),
      quality_gate_status: randomItem(['OK', 'WARN', 'ERROR']),
      analyzed_at: completedAt.toISOString(),
    },
    risk_assessment: {
      build_id: id,
      risk_level: riskLevel,
      risk_score: Number((riskPalette[riskLevel].score + Math.random() * 0.05).toFixed(2)),
      uncertainty: Number((riskPalette[riskLevel].uncertainty + Math.random() * 0.03).toFixed(2)),
      calculated_at: completedAt.toISOString(),
    },
  }

  return build
}

export const generateMockBuilds = (count = 18): BuildDetail[] => {
  return Array.from({ length: count }, (_, idx) => generateMockBuild(idx + 1))
}

export const mockBuilds = generateMockBuilds()

export const selectBuildById = (id: number): BuildDetail | undefined => {
  return mockBuilds.find((build) => build.id === id)
}

export const getBuildSummaryMetrics = (builds: BuildDetail[]) => {
  const totalBuilds = builds.length
  const recentBuilds = builds.slice(0, 8)

  const riskCounts = builds.reduce(
    (acc, build) => {
      const level = build.risk_assessment?.risk_level ?? 'low'
      acc[level] += 1
      return acc
    },
    { low: 0, medium: 0, high: 0, critical: 0 } as Record<RiskLevel, number>,
  )

  const averageScore =
    builds.reduce((sum, build) => sum + (build.risk_assessment?.risk_score ?? 0), 0) / builds.length

  const failedBuilds = builds.filter((build) => build.conclusion === 'failure').length
  const successRate = totalBuilds > 0 ? ((totalBuilds - failedBuilds) / totalBuilds) * 100 : 0

  return {
    totalBuilds,
    recentBuilds,
    riskCounts,
    averageRiskScore: Number(averageScore.toFixed(2)),
    successRate: Number(successRate.toFixed(1)),
  }
}

export const getTrendsData = (builds: BuildDetail[]) => {
  const today = new Date()
  const trendRange = Array.from({ length: 10 }, (_, idx) => subDays(today, idx)).reverse()

  return trendRange.map((day) => {
    const dayBuilds = builds.filter((build) => {
      if (!build.completed_at) return false
      const completed = new Date(build.completed_at)
      return (
        completed.getDate() === day.getDate() &&
        completed.getMonth() === day.getMonth() &&
        completed.getFullYear() === day.getFullYear()
      )
    })

    const averageRisk =
      dayBuilds.reduce((sum, build) => sum + (build.risk_assessment?.risk_score ?? 0), 0) /
      (dayBuilds.length || 1)

    return {
      date: day.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' }),
      builds: dayBuilds.length,
      riskScore: Number((averageRisk || 0.25 + Math.random() * 0.6).toFixed(2)),
      failures: dayBuilds.filter((build) => build.conclusion === 'failure').length,
    }
  })
}

export const getRepoDistribution = (builds: BuildDetail[]) => {
  const repoMap = new Map<string, { builds: number; highRisk: number }>()

  builds.forEach((build) => {
    const repo = build.repository
    if (!repoMap.has(repo)) {
      repoMap.set(repo, { builds: 0, highRisk: 0 })
    }
    const repoStats = repoMap.get(repo)!
    repoStats.builds += 1
    if (build.risk_assessment && ['high', 'critical'].includes(build.risk_assessment.risk_level)) {
      repoStats.highRisk += 1
    }
  })

  return Array.from(repoMap.entries()).map(([name, stats]) => ({
    repository: name,
    builds: stats.builds,
    highRisk: stats.highRisk,
  }))
}

export const getRiskHeatmap = (builds: BuildDetail[]) => {
  const lastSevenDays = Array.from({ length: 7 }, (_, idx) => subDays(new Date(), idx)).reverse()
  const riskByDay = lastSevenDays.map((day) => {
    const dayBuilds = builds.filter((build) => {
      if (!build.completed_at) return false
      const completed = new Date(build.completed_at)
      return (
        completed.getDate() === day.getDate() &&
        completed.getMonth() === day.getMonth() &&
        completed.getFullYear() === day.getFullYear()
      )
    })

    const riskMix = riskLevels.reduce(
      (acc, level) => {
        acc[level] = dayBuilds.filter((build) => build.risk_assessment?.risk_level === level).length
        return acc
      },
      {} as Record<RiskLevel, number>,
    )

    return {
      day: day.toLocaleDateString('vi-VN', { weekday: 'short' }),
      ...riskMix,
    }
  })

  return riskByDay
}

export const getMockGithubUsage = () => {
  return {
    connected: true,
    organization: 'buildguard',
    connectedAt: subDays(new Date(), 12).toISOString(),
    scopes: ['read:user', 'repo', 'read:org', 'workflow'],
    repositories: repositories.map((repo) => ({
      name: repo.name,
      lastSync: subDays(new Date(), Math.floor(Math.random() * 5)).toISOString(),
      buildCount: randomNumber(40, 160),
      highRiskCount: randomNumber(2, 12),
      status: randomItem(['healthy', 'degraded', 'attention']) as 'healthy' | 'degraded' | 'attention',
    })),
    lastSyncStatus: randomItem(['success', 'warning', 'error']) as 'success' | 'warning' | 'error',
    lastSyncMessage: randomItem([
      'Data synced successfully · 38 new workflow runs imported',
      'Partial sync · Some workflow runs failed to fetch logs',
      'Sync stalled · Token re-authorization required',
    ]),
  }
}

export const githubOAuthConfig = {
  authorizeUrl: 'https://github.com/login/oauth/authorize',
  clientId: 'FAKE_CLIENT_ID',
  scopes: ['read:user', 'repo', 'read:org', 'workflow'],
  redirectUri: 'http://localhost:3000/oauth/callback',
  instructions: [
    'BuildGuard chỉ sử dụng token đọc (read-only) để truy cập workflow và commit metadata.',
    'Không cần cấu hình GitHub App hoặc webhook, chỉ cần xác thực OAuth là đủ.',
    'Bạn có thể thu hồi truy cập bất kỳ lúc nào trong GitHub Settings → Applications.',
  ],
}
