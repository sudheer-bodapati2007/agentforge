import { CircleAlert, CircleCheck, Database, KeyRound, Link2 } from 'lucide-react'
import { migrated, type DatabaseReport, type SchemaTable } from '@/domain/run'
import { EmptyState } from '../ui/States'
import { Badge } from '../ui/StatusBadge'

function TableCard({ table }: { table: SchemaTable }) {
  return (
    <section aria-label={`Table ${table.name}`} className="rounded-md border border-line bg-canvas">
      <h3 className="flex items-center gap-2 border-b border-line px-3 py-2 font-mono text-[13px] text-fg">
        <Database className="size-3.5 text-fg-muted" aria-hidden />
        {table.name}
      </h3>
      <table className="w-full text-xs">
        <caption className="sr-only">Columns of {table.name}</caption>
        <thead>
          <tr className="text-left text-[11px] text-fg-subtle">
            <th scope="col" className="px-3 py-1 font-medium">Column</th>
            <th scope="col" className="px-3 py-1 font-medium">Type</th>
            <th scope="col" className="px-3 py-1 font-medium">Null</th>
            <th scope="col" className="px-3 py-1 font-medium">Default</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line font-mono">
          {table.columns.map((c) => (
            <tr key={c.name}>
              <td className="px-3 py-1 text-fg">
                <span className="flex items-center gap-1.5">
                  {c.primary_key && <KeyRound className="size-3 text-warning" aria-label="primary key" />}
                  {c.name}
                </span>
              </td>
              <td className="px-3 py-1 text-fg-muted">{c.type.toLowerCase()}</td>
              <td className="px-3 py-1 text-fg-subtle">{c.nullable ? 'yes' : 'no'}</td>
              <td className="max-w-[12rem] truncate px-3 py-1 text-fg-subtle" title={c.default ?? undefined}>
                {c.default ?? ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {(table.foreign_keys.length > 0 || table.unique.length > 0 || table.indexes.length > 0) && (
        <ul className="space-y-0.5 border-t border-line px-3 py-2 text-[11px] text-fg-muted">
          {table.foreign_keys.map((fk) => (
            <li key={fk.columns.join()} className="flex items-center gap-1.5">
              <Link2 className="size-3" aria-hidden />
              <span className="font-mono">{fk.columns.join(', ')}</span> → <span className="font-mono">{fk.references}</span>
            </li>
          ))}
          {table.unique.map((cols) => (
            <li key={`u-${cols.join()}`}>
              unique <span className="font-mono">({cols.join(', ')})</span>
            </li>
          ))}
          {table.indexes.map((ix) => (
            <li key={ix.name}>
              index <span className="font-mono">{ix.name}</span> ({ix.columns.join(', ')}){ix.unique ? ', unique' : ''}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** The project's real database after the latest test run: migrations, then the schema read back from PostgreSQL. */
export function DatabasePanel({ report, attempt }: { report: DatabaseReport | null | undefined; attempt: number | null }) {
  if (!report) {
    return <EmptyState icon={<Database className="size-5" />} title="No database results yet" description="Migrations run against a throwaway PostgreSQL before each test run." />
  }
  const ok = migrated(report)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
        <Badge tone={ok ? 'success' : 'danger'}>{ok ? 'Migrations applied' : 'Migrations failed'}</Badge>
        <span>PostgreSQL 17 · test run {attempt}</span>
        <span className="text-fg-subtle">Schema read back from the real database, not from the model.</span>
      </div>
      {report.error && (
        <p role="alert" className="rounded-md border border-danger/25 bg-danger-soft p-3 font-mono text-xs text-fg">
          {report.error}
        </p>
      )}
      <ol aria-label="Migrations" className="space-y-1.5">
        {report.migrations.length === 0 && <li className="text-xs text-fg-subtle">No migration files.</li>}
        {report.migrations.map((m) => (
          <li key={m.file} className="rounded-md border border-line bg-canvas px-3 py-2 text-xs">
            <span className="flex items-center gap-2 font-mono text-fg">
              {m.ok ? <CircleCheck className="size-3.5 text-success" aria-label="applied" /> : <CircleAlert className="size-3.5 text-danger" aria-label="failed" />}
              db/migrations/{m.file}
            </span>
            {m.error && <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-danger">{m.error}</pre>}
          </li>
        ))}
      </ol>
      {report.schema.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {report.schema.map((t) => (
            <TableCard key={t.name} table={t} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-fg-subtle">The database has no tables.</p>
      )}
    </div>
  )
}
