import type { RunStatus } from './run'

export const LANGUAGES = ['python', 'typescript', 'javascript'] as const
export type ProgrammingLanguage = (typeof LANGUAGES)[number]

export const LANGUAGE_LABELS: Record<ProgrammingLanguage, string> = {
  python: 'Python',
  typescript: 'TypeScript',
  javascript: 'JavaScript',
}

/** Mirrors the backend domain invariants (app/domain/project.py). The backend stays authoritative. */
export const PROJECT_RULES = {
  nameMax: 120,
  requirementsMin: 20,
  requirementsMax: 20_000,
  optionMax: 80,
  constraintsMax: 5_000,
} as const

export interface Project {
  id: string
  name: string
  requirements: string
  language: ProgrammingLanguage
  framework: string | null
  databasePreference: string | null
  constraints: string | null
  createdAt: Date
  updatedAt: Date
  runCount: number
  latestRunStatus: RunStatus | null
}

export interface ProjectDraft {
  name: string
  requirements: string
  language: ProgrammingLanguage
  framework: string
  databasePreference: string
  constraints: string
}

export interface ProjectPage {
  items: Project[]
  total: number
}

export type ProjectDraftErrors = Partial<Record<keyof ProjectDraft, string>>

export const EMPTY_DRAFT: ProjectDraft = {
  name: '',
  requirements: '',
  language: 'python',
  framework: '',
  databasePreference: '',
  constraints: '',
}

export function draftFromProject(project: Project): ProjectDraft {
  return {
    name: project.name,
    requirements: project.requirements,
    language: project.language,
    framework: project.framework ?? '',
    databasePreference: project.databasePreference ?? '',
    constraints: project.constraints ?? '',
  }
}

export function validateProjectDraft(draft: ProjectDraft): ProjectDraftErrors {
  const errors: ProjectDraftErrors = {}
  const name = draft.name.trim()
  const requirements = draft.requirements.trim()

  if (!name) errors.name = 'Project name is required'
  else if (name.length > PROJECT_RULES.nameMax)
    errors.name = `Use at most ${PROJECT_RULES.nameMax} characters`

  if (requirements.length < PROJECT_RULES.requirementsMin)
    errors.requirements = `Describe the software in at least ${PROJECT_RULES.requirementsMin} characters`
  else if (requirements.length > PROJECT_RULES.requirementsMax)
    errors.requirements = `Use at most ${PROJECT_RULES.requirementsMax.toLocaleString()} characters`

  if (draft.framework.trim().length > PROJECT_RULES.optionMax)
    errors.framework = `Use at most ${PROJECT_RULES.optionMax} characters`
  if (draft.databasePreference.trim().length > PROJECT_RULES.optionMax)
    errors.databasePreference = `Use at most ${PROJECT_RULES.optionMax} characters`
  if (draft.constraints.trim().length > PROJECT_RULES.constraintsMax)
    errors.constraints = `Use at most ${PROJECT_RULES.constraintsMax.toLocaleString()} characters`

  return errors
}
