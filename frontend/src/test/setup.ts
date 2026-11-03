import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// Generous async budget so tests stay deterministic on slow or loaded machines (CI, laptops).
configure({ asyncUtilTimeout: 3000 })

// Browser APIs React Flow needs that jsdom does not implement.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.DOMMatrixReadOnly ??= class {
  m22 = 1
  constructor(_transform?: string) {}
} as unknown as typeof DOMMatrixReadOnly
Element.prototype.scrollIntoView ??= function () {}

afterEach(() => cleanup())
