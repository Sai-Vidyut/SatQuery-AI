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
import { shouldShowRegionInterpretation } from "@/lib/regionInterpretation";
import { regionChatProviderBadge, regionChatTurnRole } from "@/lib/regionChatLabels";
import { geoChatDrawerHint, geoChatDrawerTitle } from "@/lib/geoChatDrawer";

type Props = {
  sessionId: string;
  result: AnalysisResult;
  selectedRegion: EvidenceRegion;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
};

function chatProviderBadge(chat: BiTemporalRegionChatResult): string {
  return regionChatProviderBadge(chat);
}

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

export function RegionGeoChatConversation({
  sessionId,
  result,
  selectedRegion,
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
  }, [selectedRegion.id, sessionId]);

  if (!shouldShowRegionInterpretation(result, selectedRegion)) {
    return null;
  }

  async function handleSend() {
    const trimmed = message.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.chatChangeRegion(sessionId, selectedRegion.id, trimmed);
      setLatestChat(response.chat);
      setMessage("");
    } catch (err) {
      setError(normalizeAnalysisError(err));
    } finally {
      setLoading(false);
    }
  }

  const turns = latestChat?.conversation.turns ?? [];
  const mode = "bi_temporal_region" as const;

  return (
    <GeoChatDrawerShell
      title={geoChatDrawerTitle(mode)}
      hint={geoChatDrawerHint(mode, selectedRegion)}
      message={message}
      onMessageChange={setMessage}
      onSend={() => void handleSend()}
      loading={loading}
      error={error}
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
            {chatProviderBadge(latestChat)}
          </p>
          {latestChat.scope_limited ? (
            <p
              className="inspector-note inspector-note--warning"
              data-testid="region-chat-scope-limited"
            >
              This conversation is limited to the selected region. Submit a new analysis to
              investigate other areas.
            </p>
          ) : null}
          <dl className="m-0 mt-2">
            <div className="inspector-metric-row">
              <dt>Conversation</dt>
              <dd>{latestChat.conversation_id.slice(0, 8)}…</dd>
            </div>
            <div className="inspector-metric-row">
              <dt>Turn</dt>
              <dd>{latestChat.turn_index + 1}</dd>
            </div>
            {!latestChat.scope_limited ? (
              <>
                <div className="inspector-metric-row">
                  <dt>Route</dt>
                  <dd data-testid="region-chat-route">{latestChat.route}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Provider</dt>
                  <dd>{latestChat.provider}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Model</dt>
                  <dd>{latestChat.model_name}</dd>
                </div>
              </>
            ) : null}
          </dl>
        </div>
      ) : null}
    </GeoChatDrawerShell>
  );
}
