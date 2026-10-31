import React, { useState, useEffect } from 'react';
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
}

type ToastListener = (toast: ToastItem) => void;
const listeners: Set<ToastListener> = new Set();

export const toast = {
  success: (message: string, title?: string) => {
    const item: ToastItem = {
      id: Math.random().toString(36).substring(2, 9),
      type: 'success',
      title,
      message,
    };
    listeners.forEach((l) => l(item));
  },
  error: (message: string, title?: string) => {
    const item: ToastItem = {
      id: Math.random().toString(36).substring(2, 9),
      type: 'error',
      title,
      message,
    };
    listeners.forEach((l) => l(item));
  },
  info: (message: string, title?: string) => {
    const item: ToastItem = {
      id: Math.random().toString(36).substring(2, 9),
      type: 'info',
      title,
      message,
    };
    listeners.forEach((l) => l(item));
  },
};

export const ToastContainer: React.FC = () => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const handler: ToastListener = (newToast) => {
      setToasts((prev) => [...prev, newToast]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== newToast.id));
      }, 3500);
    };

    listeners.add(handler);
    return () => {
      listeners.delete(handler);
    };
  }, []);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col space-y-2.5 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => {
        const isSuccess = t.type === 'success';
        const isError = t.type === 'error';

        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start space-x-3 p-3.5 rounded-xl shadow-xl border backdrop-blur-md transition-all transform translate-y-0 animate-in fade-in slide-in-from-top-2 duration-200 ${
              isSuccess
                ? 'bg-slate-900/95 border-emerald-500/30 text-slate-100 shadow-emerald-500/10'
                : isError
                ? 'bg-slate-900/95 border-rose-500/30 text-slate-100 shadow-rose-500/10'
                : 'bg-slate-900/95 border-indigo-500/30 text-slate-100 shadow-indigo-500/10'
            }`}
          >
            <div className="flex-shrink-0 mt-0.5">
              {isSuccess && <CheckCircle className="w-5 h-5 text-emerald-400" />}
              {isError && <AlertCircle className="w-5 h-5 text-rose-400" />}
              {!isSuccess && !isError && <Info className="w-5 h-5 text-indigo-400" />}
            </div>

            <div className="flex-1 min-w-0 pr-1">
              {t.title && (
                <p
                  className={`text-xs font-bold mb-0.5 ${
                    isSuccess ? 'text-emerald-300' : isError ? 'text-rose-300' : 'text-indigo-300'
                  }`}
                >
                  {t.title}
                </p>
              )}
              <p className="text-xs text-slate-200 leading-relaxed break-words">{t.message}</p>
            </div>

            <button
              onClick={() => removeToast(t.id)}
              className="text-slate-400 hover:text-slate-200 p-0.5 rounded transition flex-shrink-0"
              aria-label="Dismiss notification"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
