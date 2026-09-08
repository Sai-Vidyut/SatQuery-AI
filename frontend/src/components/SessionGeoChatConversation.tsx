"use client";

import { useEffect, useState } from "react";
import type {
  AnalysisResult,
  BiTemporalRegionChatResult,
  ConversationTurnRecord,
  EvidenceRegion,
} from "@/types/domain";
import { GeoChatDrawerShell } from "@/components/GeoChatDrawerShell";
import { api } from "@/lib/api";
import { normalizeAnalysisError } from "@/lib/errors";
import {
  type GeoChatDrawerMode,
  geoChatDrawerHint,
  geoChatDrawerTitle,
} from "@/lib/geoChatDrawer";
import { regionChatProviderBadge, regionChatTurnRole } from "@/lib/regionChatLabels";

type Props = {
  sessionId: string;
  result: AnalysisResult;
  mode: GeoChatDrawerMode;
  selectedRegion: EvidenceRegion | null;
  selectedRegionId: string | null;
  chatResetKey: number;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
};

function TurnHistory({ turns }: { turns: ConversationTurnRecord[] }) {
  if (turns.length === 0) return null;
  return (
    <ol className="region-chat__history" data-testid="region-chat-history">
      {turns.map((turn) => (
        <li key={turn.turn_id} className="region-chat__turn" data-testid="region-chat-turn">
          <p className="region-chat__role">You</p>
          <p className="region-chat__message">{turn.user_message}</p>
          <p className="region-chat__role">{regionChatTurnRole(turn)}</p>
          <p className="region-chat__answer">{turn.assistant_answer}</p>
        </li>
      ))}
    </ol>
  );
}

export function SessionGeoChatConversation({
  sessionId,
  result,
  mode,
  selectedRegion,
  selectedRegionId,
  chatResetKey,
  expanded,
  onExpandedChange,
}: Props) {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestChat, setLatestChat] = useState<BiTemporalRegionChatResult | null>(null);

  useEffect(() => {
    setLatestChat(null);
    setError(null);
    setLoading(false);
    setMessage("");
  }, [chatResetKey, mode, selectedRegionId, sessionId]);

  const waitingForRegion = mode === "bi_temporal_region" && !selectedRegion;

  async function handleSend() {
    const trimmed = message.trim();
    if (!trimmed || waitingForRegion) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.chatSession(sessionId, trimmed, selectedRegionId);
      setLatestChat(response.chat);
      setMessage("");
    } catch (err) {
      setError(normalizeAnalysisError(err));
    } finally {
      setLoading(false);
    }
  }

  const turns = latestChat?.conversation.turns ?? [];

  return (
    <GeoChatDrawerShell
      title={geoChatDrawerTitle(mode)}
      hint={geoChatDrawerHint(mode, selectedRegion)}
      message={message}
      onMessageChange={setMessage}
      onSend={() => void handleSend()}
      loading={loading}
      error={error}
      sendDisabled={waitingForRegion}
      placeholder={
        waitingForRegion
          ? "Select a region to enable GeoChat…"
          : "Ask GeoChat a follow-up question…"
      }
      expanded={expanded}
      onExpandedChange={onExpandedChange}
    >
      <TurnHistory turns={turns} />

      {latestChat ? (
        <div className="region-chat__meta" data-testid="region-chat-latest">
          <p
            className="region-interpretation__badge"
            data-testid="region-chat-provider-badge"
            data-route={latestChat.route}
            data-provider={latestChat.provider}
          >
            {regionChatProviderBadge(latestChat)}
          </p>
          {latestChat.scope_limited ? (
            <p
              className="inspector-note inspector-note--warning"
              data-testid="region-chat-scope-limited"
            >
              This follow-up is limited to the current analysis result. Submit a new analysis to
              explore further.
            </p>
          ) : null}
        </div>
      ) : null}
    </GeoChatDrawerShell>
  );
}
