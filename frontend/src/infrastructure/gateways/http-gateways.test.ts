import { describe, expect, it, vi } from 'vitest'
import { AppError } from '@/application/errors'
import { EMPTY_DRAFT } from '@/domain/project'
import type { HttpClient } from '../http/http-client'
import { createEvaluationGateway, createProjectGateway } from './http-gateways'

describe('evaluation gateway', () => {
  it('maps benchmarks to the domain and passes the limit', async () => {
    const request = vi.fn(async () => ({
      benchmarks: [
        {
          id: 'b1',
          created_at: '2026-10-22T14:00:00Z',
          model_names: ['m'],
          demo_model: false,
          summaries: [{ system: 'multi_agent', solve_rate: null, total_cost_usd: null }],
          results: [
            {
              task_id: 'crud',
              own_tests: { executed: true, passed: 2, total: 3, errors: 0 },
              reference_tests: { executed: false, passed: 0, total: 0, errors: 0 },
              estimated_cost_usd: null,
            },
          ],
        },
      ],
    }))
    const [benchmark] = await createEvaluationGateway({ request } as unknown as HttpClient).recent(3)
    expect(request).toHaveBeenCalledWith('GET', '/evaluations', { query: { limit: 3 } })
    expect(benchmark.createdAt).toEqual(new Date('2026-10-22T14:00:00Z'))
    expect(benchmark.modelNames).toEqual(['m'])
    expect(benchmark.summaries[0]).toEqual({ system: 'multi_agent', solveRate: null, totalCostUsd: null })
    expect(benchmark.results[0].ownTests).toEqual({ executed: true, passed: 2, total: 3, errors: 0 })
    expect(benchmark.results[0].referenceTests.executed).toBe(false)
    expect(benchmark.results[0].estimatedCostUsd).toBeNull()
  })
})

const dto = {
  id: '1',
  name: 'A',
  requirements: 'r'.repeat(20),
  language: 'python',
  framework: null,
  database_preference: null,
  constraints: null,
  created_at: '2026-10-01T10:00:00Z',
  updated_at: '2026-10-01T10:00:00Z',
  run_count: 0,
  latest_run_status: null,
}

describe('project gateway', () => {
  it('sends snake_case bodies and nulls blank optional fields', async () => {
    const request = vi.fn(async () => dto)
    const gateway = createProjectGateway({ request } as unknown as HttpClient)
    const project = await gateway.create({
      ...EMPTY_DRAFT,
      name: ' A ',
      requirements: 'r'.repeat(20),
      databasePreference: '  ',
    })
    expect(request).toHaveBeenCalledWith('POST', '/projects', {
      body: {
        name: 'A',
        requirements: 'r'.repeat(20),
        language: 'python',
        framework: null,
        database_preference: null,
        constraints: null,
      },
    })
    expect(project.createdAt).toBeInstanceOf(Date)
  })

  it('re-keys server field errors to draft field names', async () => {
    const request = vi.fn(async () => {
      throw new AppError('validation', 'bad', {
        status: 422,
        fieldErrors: [{ field: 'database_preference', message: 'too long' }],
      })
    })
    const gateway = createProjectGateway({ request } as unknown as HttpClient)
    const error = (await gateway.update('1', { databasePreference: 'x' }).catch((e: unknown) => e)) as AppError
    expect(error.fieldErrors).toEqual([{ field: 'databasePreference', message: 'too long' }])
  })
})
