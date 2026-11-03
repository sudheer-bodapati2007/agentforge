import { ShieldCheck } from 'lucide-react'
import { useSystemStatus } from '@/application/use-cases/system'
import { PageHeader } from '../components/PageHeader'
import { SystemReadiness } from '../components/SystemReadiness'
import { Panel } from '../components/ui/Panel'
import { ErrorState, LoadingBlock } from '../components/ui/States'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-xs text-fg-subtle">{label}</dt>
      <dd className="font-mono text-[13px] text-fg">{value}</dd>
    </div>
  )
}

export function SettingsPage() {
  const query = useSystemStatus()
  const status = query.data

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Settings" description="Live configuration reported by the backend." />

      {query.isError ? (
        <ErrorState error={query.error} title="Could not reach the backend" onRetry={() => query.refetch()} />
      ) : !status ? (
        <LoadingBlock label="Loading settings" rows={6} />
      ) : (
        <>
          <Panel title="Components" bodyClassName="py-1">
            <SystemReadiness status={status} />
          </Panel>

          <Panel title="Runtime" bodyClassName="py-1">
            <dl className="divide-y divide-line">
              <Row label="Version" value={status.version} />
              <Row label="Environment" value={status.environment} />
              <Row label="Database backend" value={status.databaseBackend} />
              <Row label="LLM provider" value={status.llm.provider ?? 'not set'} />
              <Row label="LLM model" value={status.llm.model ?? 'not set'} />
              <Row label="LLM API key" value={status.llm.apiKeyPresent ? 'present (hidden)' : 'missing'} />
              <Row label="Max debug iterations" value={String(status.maxDebugIterations)} />
            </dl>
          </Panel>

          <div className="flex gap-3 rounded-lg border border-line bg-panel p-4 text-[13px] text-fg-muted">
            <ShieldCheck className="size-5 shrink-0 text-accent" aria-hidden />
            <p>
              Configuration is set through server environment variables (see <code className="font-mono text-fg">.env.example</code>).
              Secrets never reach the browser; the API only reports whether a key is present.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
