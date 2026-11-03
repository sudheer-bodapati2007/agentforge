import type { RunStatus } from './run'

export interface RecentRun {
  id: string
  projectId: string
  projectName: string
  status: RunStatus
  createdAt: Date
  durationSeconds: number | null
}

export interface RecentProject {
  id: string
  name: string
  updatedAt: Date
}

/** `null` means "no data to compute this from" and must never be shown as zero. */
export interface DashboardMetrics {
  totalProjects: number
  totalRuns: number
  runsByStatus: Record<RunStatus, number>
  completionRate: number | null
  testPassRate: number | null
  executedTestSuites: number
  averageDurationSeconds: number | null
  totalEstimatedCostUsd: number | null
  recentRuns: RecentRun[]
  recentProjects: RecentProject[]
}
