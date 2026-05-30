import { Play, Pause, Square, AlertTriangle, BarChart3 } from 'lucide-react'
import type { ExecutionStatus } from '../types/execution'

interface StatusCardsProps {
  status: ExecutionStatus
}

export function StatusCards({ status }: StatusCardsProps) {
  const cards = [
    {
      label: '运行中',
      value: status.running_count,
      icon: Play,
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
    },
    {
      label: '已暂停',
      value: status.paused_count,
      icon: Pause,
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
    },
    {
      label: '已停止',
      value: status.stopped_count,
      icon: Square,
      color: 'text-slate-400',
      bg: 'bg-slate-500/10',
    },
    {
      label: '今日盈亏',
      value: status.today_pnl >= 0 ? `+¥${status.today_pnl.toLocaleString()}` : `¥${status.today_pnl.toLocaleString()}`,
      icon: BarChart3,
      color: status.today_pnl >= 0 ? 'text-up' : 'text-down',
      bg: status.today_pnl >= 0 ? 'bg-up/10' : 'bg-down/10',
    },
    {
      label: '活跃告警',
      value: status.active_alerts,
      icon: AlertTriangle,
      color: status.active_alerts > 0 ? 'text-red-400' : 'text-slate-400',
      bg: status.active_alerts > 0 ? 'bg-red-500/10' : 'bg-slate-500/10',
    },
    {
      label: '今日信号',
      value: status.total_signals_today,
      icon: BarChart3,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      {cards.map((card, index) => (
        <div
          key={index}
          className="bg-surface-container-high rounded-lg p-4 border border-outline-variant/20"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-on-surface-variant">{card.label}</span>
            <card.icon className={`w-4 h-4 ${card.color}`} />
          </div>
          <div className={`text-2xl font-bold font-mono-num ${card.color}`}>
            {card.value}
          </div>
        </div>
      ))}
    </div>
  )
}
