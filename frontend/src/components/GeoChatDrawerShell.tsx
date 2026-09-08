"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import {
  GEOCHAT_DRAWER_DEFAULT_HEIGHT,
  GEOCHAT_DRAWER_MAX_HEIGHT_RATIO,
  GEOCHAT_DRAWER_MIN_HEIGHT,
  clampGeoChatDrawerHeight,
  resolveGeoChatDrawerMaxHeight,
} from "@/lib/geoChatDrawer";

type Props = {
  title: string;
  hint: string;
  message: string;
  onMessageChange: (value: string) => void;
  onSend: () => void;
  loading: boolean;
  error: string | null;
  sendDisabled?: boolean;
  placeholder?: string;
  sendLabel?: string;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  children?: ReactNode;
};

export function GeoChatDrawerShell({
  title,
  hint,
  message,
  onMessageChange,
  onSend,
  loading,
  error,
  sendDisabled = false,
  placeholder = "Ask GeoChat a follow-up question…",
  sendLabel = "Send follow-up",
  expanded,
  onExpandedChange,
  children,
}: Props) {
  const composerDisabled = loading || sendDisabled || message.trim().length === 0;
  const drawerRef = useRef<HTMLElement | null>(null);
  const [drawerHeight, setDrawerHeight] = useState(GEOCHAT_DRAWER_DEFAULT_HEIGHT);
  const dragStateRef = useRef<{ startY: number; startHeight: number } | null>(null);

  const clampHeight = useCallback((nextHeight: number) => {
    const maxHeight = resolveGeoChatDrawerMaxHeight(drawerRef.current);
    return clampGeoChatDrawerHeight(nextHeight, maxHeight);
  }, []);

  useEffect(() => {
    if (!expanded) return;
    setDrawerHeight((current) => clampHeight(current));
  }, [clampHeight, expanded]);

  useEffect(() => {
    if (!expanded) return;
    function handleResize() {
      setDrawerHeight((current) => clampHeight(current));
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [clampHeight, expanded]);

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      const drag = dragStateRef.current;
      if (!drag) return;
      const delta = drag.startY - event.clientY;
      setDrawerHeight(clampHeight(drag.startHeight + delta));
    }

    function handlePointerUp() {
      dragStateRef.current = null;
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };
  }, [clampHeight]);

  function handleResizePointerDown(event: ReactPointerEvent<HTMLButtonElement>) {
    if (!expanded) return;
    event.preventDefault();
    dragStateRef.current = {
      startY: event.clientY,
      startHeight: drawerHeight,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleResizeKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!expanded) return;
    const step = event.shiftKey ? 32 : 16;
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setDrawerHeight((current) => clampHeight(current + step));
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setDrawerHeight((current) => clampHeight(current - step));
    }
  }

  if (!expanded) {
    return (
      <section
        className="inspector-chat-drawer inspector-chat-drawer--collapsed"
        data-testid="inspector-chat-drawer"
        aria-label="GeoChat conversation"
      >
        <button
          type="button"
          className="inspector-chat-drawer__toggle"
          aria-expanded={false}
          aria-label="Open GeoChat"
          data-testid="region-chat-open"
          onClick={() => onExpandedChange(true)}
        >
          <span className="inspector-chat-drawer__toggle-copy">
            <span className="inspector-chat-drawer__toggle-title">{title}</span>
            <span className="inspector-chat-drawer__toggle-action">Open chat</span>
          </span>
          <ChevronUp size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      </section>
    );
  }

  return (
    <section
      ref={drawerRef}
      className="inspector-chat-drawer inspector-chat-drawer--expanded"
      data-testid="inspector-chat-drawer"
      aria-label="GeoChat conversation"
      style={{
        height: `${drawerHeight}px`,
        minHeight: `${GEOCHAT_DRAWER_MIN_HEIGHT}px`,
        maxHeight: `${Math.floor(
          resolveGeoChatDrawerMaxHeight(drawerRef.current) || drawerHeight * GEOCHAT_DRAWER_MAX_HEIGHT_RATIO,
        )}px`,
      }}
    >
      <button
        type="button"
        className="inspector-chat-drawer__resize-handle"
        aria-label="Resize GeoChat drawer"
        aria-valuemin={GEOCHAT_DRAWER_MIN_HEIGHT}
        aria-valuemax={resolveGeoChatDrawerMaxHeight(drawerRef.current)}
        aria-valuenow={drawerHeight}
        aria-orientation="vertical"
        data-testid="region-chat-resize-handle"
        onPointerDown={handleResizePointerDown}
        onKeyDown={handleResizeKeyDown}
      >
        <span aria-hidden="true">⋮⋮⋮</span>
      </button>

      <header className="inspector-chat-drawer__header">
        <div className="inspector-chat-drawer__header-row">
          <p className="inspector-section__label m-0">{title}</p>
          <button
            type="button"
            className="inspector-chat-drawer__collapse"
            aria-expanded={true}
            aria-label="Collapse GeoChat"
            data-testid="region-chat-collapse"
            onClick={() => onExpandedChange(false)}
          >
            <span>Collapse</span>
            <ChevronDown size={16} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
        <p className="inspector-note m-0 mt-1">{hint}</p>
      </header>

      <div className="inspector-chat-drawer__messages" data-testid="region-geochat-conversation">
        {children}
        {loading ? (
          <p className="inspector-note mt-2" data-testid="region-chat-loading">
            Running GeoChat…
          </p>
        ) : null}
        {error ? (
          <p className="inspector-note inspector-note--error mt-2" data-testid="region-chat-error">
            {error}
          </p>
        ) : null}
      </div>

      <div className="inspector-chat-drawer__composer">
        <label className="inspector-section__label" htmlFor="region-chat-message">
          Message
        </label>
        <textarea
          id="region-chat-message"
          className="region-interpretation__question"
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          rows={3}
          data-testid="region-chat-message"
          placeholder={placeholder}
          disabled={sendDisabled && !loading}
        />
        <button
          type="button"
          className="geochat-send-btn mt-2"
          onClick={onSend}
          disabled={composerDisabled}
          data-testid="region-chat-send"
        >
          {loading ? "Sending…" : sendLabel}
        </button>
      </div>
    </section>
  );
}
