// ✅ DO
import { cn } from '@/utils/cn';

export function Panel({ className, ...props }: PanelProps) {
  return (
    <div
      className={cn(
        'glass-panel rounded-xl shadow-md',
        'min-w-[300px] min-h-[200px]',
        'resize-x resize-y',
        className
      )}
      {...props}
    />
  );
}

// ❌ DON'T
export function Panel(props) {
  return (
    <div 
      style={{
        background: 'rgba(24, 26, 31, 0.7)',
        backdropFilter: 'blur(20px)',
        minWidth: '300px'
      }}
      {...props}
    />
  );
}