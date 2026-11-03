import { useNavigate } from 'react-router-dom'
import { useCreateProject } from '@/application/use-cases/projects'
import { EMPTY_DRAFT } from '@/domain/project'
import { PageHeader } from '../components/PageHeader'
import { ProjectForm } from '../components/ProjectForm'
import { Panel } from '../components/ui/Panel'
import { useToast } from '../components/ui/Toast'

export function NewProjectPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const create = useCreateProject()

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title="New project"
        description="Describe what to build. You can review and refine the requirements before running a workflow."
      />
      <Panel>
        <ProjectForm
          initial={EMPTY_DRAFT}
          submitLabel="Create project"
          submitting={create.isPending}
          serverError={create.error}
          onCancel={() => navigate('/projects')}
          onSubmit={(draft) =>
            create.mutate(draft, {
              onSuccess: (project) => {
                toast.success(`Project “${project.name}” created`)
                navigate(`/projects/${project.id}`)
              },
            })
          }
        />
      </Panel>
    </div>
  )
}
