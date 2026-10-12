import { useCallback, useRef, useState, type MouseEvent, type ReactNode } from 'react';

interface ContextMenuItem {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  icon?: ReactNode;
  danger?: boolean;
}

interface ContextMenuState {
  x: number;
  y: number;
  items: ContextMenuItem[];
  visible: boolean;
}

export function useContextMenu() {
  const [state, setState] = useState<ContextMenuState>({
    x: 0,
    y: 0,
    items: [],
    visible: false,
  });
  const anchorRef = useRef<HTMLDivElement | null>(null);

  const open = useCallback(
    (event: MouseEvent<HTMLElement>, items: ContextMenuItem[]) => {
      event.preventDefault();
      event.stopPropagation();
      const target = event.currentTarget;
      const rect = target.getBoundingClientRect();
      setState({
        x: rect.left,
        y: rect.bottom + 4,
        items,
        visible: true,
      });
    },
    []
  );

  const openAt = useCallback(
    (event: MouseEvent<HTMLElement>, items: ContextMenuItem[]) => {
      event.preventDefault();
      event.stopPropagation();
      setState({
        x: event.clientX,
        y: event.clientY + 4,
        items,
        visible: true,
      });
    },
    []
  );

  const close = useCallback(() => {
    setState((s) => ({ ...s, visible: false }));
  }, []);

  return {
    state,
    open,
    openAt,
    close,
    anchorRef,
  };
}