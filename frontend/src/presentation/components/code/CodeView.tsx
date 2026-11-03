import clsx from 'clsx'
import { Highlight, themes } from 'prism-react-renderer'
import { useEffect, useRef } from 'react'
import type { Severity } from '@/domain/run'
import { languageFor } from '../../lib/code'
import { SEVERITY_DOT } from '../../lib/severity'

export interface LineAnnotation {
  line: number
  severity: Severity
  title: string
  source: 'tool' | 'llm'
}

function Note({ note, suffix }: { note: LineAnnotation; suffix?: string }) {
  return (
    <div role="note" className="my-0.5 ml-[3.75rem] mr-3 rounded border-l-2 border-warning bg-elevated px-2 py-0.5 font-sans text-[11px] whitespace-normal text-fg">
      <span className="mr-1.5 font-medium uppercase text-fg-muted">{note.severity}</span>
      {note.title}
      <span className="ml-1.5 text-fg-subtle">
        ({note.source === 'tool' ? 'tool' : 'LLM reviewer'}
        {suffix ? `; ${suffix}` : ''})
      </span>
    </div>
  )
}

/**
 * Read-only, syntax-highlighted source with line numbers (rendered as text, never as HTML).
 * Review findings appear under the line they refer to; `highlightLine` is scrolled into view.
 */
export function CodeView({
  path,
  code,
  highlightLine,
  annotations = [],
}: {
  path: string
  code: string
  highlightLine?: number | null
  annotations?: LineAnnotation[]
}) {
  const target = useRef<HTMLDivElement>(null)
  useEffect(() => {
    target.current?.scrollIntoView({ block: 'center' })
  }, [highlightLine, path])

  const byLine = new Map<number, LineAnnotation[]>()
  for (const a of annotations) byLine.set(a.line, [...(byLine.get(a.line) ?? []), a])

  return (
    <Highlight theme={themes.vsDark} code={code.replace(/\n$/, '')} language={languageFor(path)}>
      {({ tokens, getLineProps, getTokenProps }) => (
        <pre className="min-w-max py-2 font-mono text-[12px] leading-[1.6]" style={{ background: 'transparent' }}>
          {tokens.map((line, index) => {
            const lineProps = getLineProps({ line })
            const number = index + 1
            const notes = byLine.get(number) ?? []
            return (
              <div key={index}>
                <div
                  {...lineProps}
                  ref={number === highlightLine ? target : undefined}
                  data-line={number}
                  className={clsx(lineProps.className, 'flex px-3', number === highlightLine && 'bg-warning-soft')}
                >
                  <span className="mr-1 inline-flex w-3 shrink-0 items-center" aria-hidden>
                    {notes.length > 0 && <span className={clsx('size-1.5 rounded-full', SEVERITY_DOT[notes[0].severity])} />}
                  </span>
                  <span className="mr-4 inline-block w-8 shrink-0 text-right text-fg-subtle select-none">{number}</span>
                  <span>
                    {line.map((token, key) => (
                      <span key={key} {...getTokenProps({ token })} />
                    ))}
                  </span>
                </div>
                {notes.map((note, i) => (
                  <Note key={i} note={note} />
                ))}
              </div>
            )
          })}
          {/* A finding may cite a line past the end (models miscount); show it rather than drop it. */}
          {annotations
            .filter((a) => a.line > tokens.length)
            .map((note, i) => (
              <Note key={`beyond-${i}`} note={note} suffix={`line ${note.line} is past the end of the file`} />
            ))}
        </pre>
      )}
    </Highlight>
  )
}
