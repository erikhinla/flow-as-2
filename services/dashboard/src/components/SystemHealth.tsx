import { apiFetch } from '../lib/api'
import { useQuery } from '@tanstack/react-query'
import { Activity, AlertCircle, CheckCircle } from 'lucide-react'

interface HealthStatus {
  status: string
  timestamp: string
  version?: string
}

export function SystemHealth() {
  const { data: health, isLoading } = useQuery<HealthStatus>({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await apiFetch('/api/health')
      if (!response.ok) throw new Error('Health check failed')
      return response.json()
    },
    refetchInterval: 5000, // Check every 5 seconds
  })

  const { data: flowHealth } = useQuery({
    queryKey: ['flow-health'],
    queryFn: async () => {
      const response = await apiFetch('/api/flow/health')
      if (!response.ok) throw new Error('Flow health check failed')
      return response.json()
    },
    refetchInterval: 10000, // Check every 10 seconds
  })

  const isHealthy = health?.status === 'healthy'
  const flowHealthy = flowHealth?.status === 'healthy'

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-white/55">
        <div className="h-3 w-3 animate-spin rounded-full border border-flow-accent border-t-transparent"></div>
        <span className="text-xs">Reading system</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2">
      <div className="hidden items-center gap-1.5 sm:flex">
        {isHealthy ? (
          <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <AlertCircle className="h-3.5 w-3.5 text-red-400" />
        )}
        <span className="text-xs text-white/55">API</span>
      </div>

      <div className="hidden items-center gap-1.5 sm:flex">
        {flowHealthy ? (
          <Activity className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <AlertCircle className="h-3.5 w-3.5 text-red-400" />
        )}
        <span className="text-xs text-white/55">Workers</span>
      </div>

      <div className="flex items-center gap-2 border-l border-white/10 pl-3">
        <div 
          className={`h-2 w-2 rounded-full ${isHealthy && flowHealthy ? 'bg-emerald-400' : 'bg-red-400'}`}
        ></div>
        <span className="text-xs font-semibold text-white">
          {isHealthy && flowHealthy ? 'Ready' : 'Needs attention'}
        </span>
      </div>
    </div>
  )
}
