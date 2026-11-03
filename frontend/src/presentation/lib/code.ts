const LANGUAGE_BY_EXTENSION: Record<string, string> = {
  py: 'python',
  json: 'json',
  md: 'markdown',
  yaml: 'yaml',
  yml: 'yaml',
  sql: 'sql',
  css: 'css',
  html: 'markup',
  toml: 'yaml',
  ini: 'yaml',
  cfg: 'yaml',
}

export function languageFor(path: string): string {
  const extension = path.split('.').pop()?.toLowerCase() ?? ''
  return LANGUAGE_BY_EXTENSION[extension] ?? 'text'
}
