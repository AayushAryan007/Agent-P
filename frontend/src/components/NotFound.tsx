import { Compass } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState } from './ui'

export function NotFound() {
  return (
    <EmptyState icon={Compass} title="Page not found" action={<Link to="/dashboard" className="text-blue hover:underline">Back to dashboard</Link>}>
      This route does not exist.
    </EmptyState>
  )
}
