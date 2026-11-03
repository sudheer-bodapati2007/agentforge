import { Compass } from 'lucide-react'
import { ButtonLink } from '../components/ui/Button'
import { EmptyState } from '../components/ui/States'

export function NotFoundPage() {
  return (
    <EmptyState
      className="py-24"
      icon={<Compass className="size-5" />}
      title="Page not found"
      description="This page does not exist."
      action={<ButtonLink to="/">Go to dashboard</ButtonLink>}
    />
  )
}
