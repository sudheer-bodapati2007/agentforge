import { ChevronDown } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { AppError } from '@/application/errors'
import {
  LANGUAGE_LABELS,
  LANGUAGES,
  PROJECT_RULES,
  validateProjectDraft,
  type ProgrammingLanguage,
  type ProjectDraft,
  type ProjectDraftErrors,
} from '@/domain/project'
import { Button } from './ui/Button'
import { SelectField, TextAreaField, TextField } from './ui/Field'

interface ProjectFormProps {
  initial: ProjectDraft
  submitLabel: string
  submitting: boolean
  /** Server-side error from the last submit; field errors are shown inline. */
  serverError?: unknown
  onSubmit: (draft: ProjectDraft) => void
  onCancel?: () => void
}

function serverFieldErrors(error: unknown): ProjectDraftErrors {
  if (!(error instanceof AppError)) return {}
  return Object.fromEntries(error.fieldErrors.map((e) => [e.field, e.message]))
}

export function ProjectForm({ initial, submitLabel, submitting, serverError, onSubmit, onCancel }: ProjectFormProps) {
  const [draft, setDraft] = useState<ProjectDraft>(initial)
  const [touched, setTouched] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(Boolean(initial.constraints))

  const clientErrors = validateProjectDraft(draft)
  const errors: ProjectDraftErrors = { ...serverFieldErrors(serverError), ...(touched ? clientErrors : {}) }
  const requirementsLength = draft.requirements.trim().length

  const set = <K extends keyof ProjectDraft>(key: K, value: ProjectDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }))

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    if (Object.keys(clientErrors).length === 0) onSubmit(draft)
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <TextField
        label="Project name"
        value={draft.name}
        onChange={(e) => set('name', e.target.value)}
        maxLength={PROJECT_RULES.nameMax}
        placeholder="Library catalogue"
        error={errors.name}
        autoFocus
      />

      <TextAreaField
        label="Software requirements"
        value={draft.requirements}
        onChange={(e) => set('requirements', e.target.value)}
        maxLength={PROJECT_RULES.requirementsMax}
        rows={8}
        placeholder="A small library catalogue in app/library.py: add_author(name), add_book(author_id, title, year) and books_by(author_id). Author names are unique; a book's year must be after 1400. Write pytest tests."
        error={errors.requirements}
        hint={`${requirementsLength.toLocaleString()} / ${PROJECT_RULES.requirementsMax.toLocaleString()} characters. The planner agent turns this into requirements, assumptions and tasks. Small, specific requests with exact names work best.`}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <SelectField
          label="Language"
          value={draft.language}
          onChange={(e) => set('language', e.target.value as ProgrammingLanguage)}
          error={errors.language}
        >
          {LANGUAGES.map((language) => (
            <option key={language} value={language}>
              {LANGUAGE_LABELS[language]}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Framework"
          optional
          value={draft.framework}
          onChange={(e) => set('framework', e.target.value)}
          maxLength={PROJECT_RULES.optionMax}
          placeholder="FastAPI"
          error={errors.framework}
        />
        <TextField
          label="Database"
          optional
          value={draft.databasePreference}
          onChange={(e) => set('databasePreference', e.target.value)}
          maxLength={PROJECT_RULES.optionMax}
          placeholder="PostgreSQL"
          hint="PostgreSQL: a schema agent writes migrations and tests run against a real database. Empty: in-memory or SQLite."
          error={errors.databasePreference}
        />
      </div>

      <div className="rounded-md border border-line">
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
          className="flex w-full items-center justify-between px-3 py-2 text-[13px] font-medium text-fg-muted hover:text-fg"
        >
          Additional constraints
          <ChevronDown className={`size-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} aria-hidden />
        </button>
        {showAdvanced && (
          <div className="border-t border-line p-3">
            <TextAreaField
              label="Constraints"
              optional
              value={draft.constraints}
              onChange={(e) => set('constraints', e.target.value)}
              maxLength={PROJECT_RULES.constraintsMax}
              rows={4}
              placeholder="e.g. No external network calls; target Python 3.12; keep dependencies minimal."
              error={errors.constraints}
            />
          </div>
        )}
      </div>

      {serverError != null && Object.keys(serverFieldErrors(serverError)).length === 0 && (
        <p role="alert" className="text-[13px] text-danger">
          {serverError instanceof Error ? serverError.message : 'Request failed'}
        </p>
      )}

      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button variant="ghost" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" loading={submitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
