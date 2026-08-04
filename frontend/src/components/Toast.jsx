import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, XCircle } from 'lucide-react';

/**
 * Slide-in toast notification.
 * Usage: call showToast({ message, type }) from the context or parent.
 *
 * This is a self-contained controlled component.
 * @param {string}  message
 * @param {'success'|'error'} type
 * @param {Function} onDismiss
 */
export default function Toast({ message, type = 'success', onDismiss }) {
  const timerRef = useRef(null);

  useEffect(() => {
    timerRef.current = setTimeout(onDismiss, 3500);
    return () => clearTimeout(timerRef.current);
  }, [onDismiss]);

  const Icon = type === 'success' ? CheckCircle2 : XCircle;
  const border = type === 'success' ? 'border-l-green-500' : 'border-l-red-500';
  const iconColor = type === 'success' ? 'text-green-400' : 'text-red-400';

  return createPortal(
    <div
      className={`glass border-l-4 ${border} animate-slide-right flex items-center gap-3 px-5 py-4 text-sm max-w-sm`}
    >
      <Icon size={18} className={`${iconColor} shrink-0`} />
      <span className="text-slate-200">{message}</span>
    </div>,
    document.getElementById('toast-root')
  );
}
