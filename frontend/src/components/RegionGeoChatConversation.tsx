"use client";

import { useEffect, useState } from "react";
import type {
  AnalysisResult,
  BiTemporalRegionChatResult,
  ConversationTurnRecord,
  EvidenceRegion,
} from "@/types/domain";
import { api } from "@/lib/api";
import { normalizeAnalysisError } from "@/lib/errors";
import { shouldShowRegionInterpretation, regionInterpretationProviderLabel } from "@/lib/regionInterpretation";

type Props = {
  sessionId: string;
  result: AnalysisResult;
  selectedRegion: EvidenceRegion;
};

function chatProviderBadge(chat: BiTemporalRegionChatResult): string {
  if (chat.scope_limited) {
    return "SCOPE LIMITED";
  }
  return regionInterpretationProviderLabel(chat.provider);
}

function TurnHistory({ turns }: { turns: ConversationTurnRecord[] }) {
  if (turns.length === 0) return null;
  return (
    <ol className="region-chat__history" data-testid="region-chat-history">
      {turns.map((turn) => (
        <li key={turn.turn_id} className="region-chat__turn" data-testid="region-chat-turn">
          <p className="region-chat__role">You</p>
          <p className="region-chat__message">{turn.user_message}</p>
          <p className="region-chat__role">GeoChat</p>
          <p className="region-chat__answer">{turn.assistant_answer}</p>
        </li>
      ))}
    </ol>
  );
}

export function RegionGeoChatConversation({ sessionId, result, selectedRegion }: Props) {
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

  return (
    <div className="inspector-section region-chat" data-testid="region-geochat-conversation">
      <p className="inspector-section__label">GeoChat follow-up</p>
      <p className="inspector-note mb-2">
        Ask follow-up questions about this selected region only. Out-of-scope requests stay
        region-limited and do not run new detection.
      </p>

      <TurnHistory turns={turns} />

      {latestChat ? (
        <div className="region-chat__meta mt-2" data-testid="region-chat-latest">
          <p
            className="region-interpretation__badge"
            data-testid="region-chat-provider-badge"
          >
            {chatProviderBadge(latestChat)}
          </p>
          {latestChat.scope_limited ? (
            <p className="inspector-note inspector-note--warning" data-testid="region-chat-scope-limited">
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

      <label className="inspector-section__label mt-3" htmlFor="region-chat-message">
        Message
      </label>
      <textarea
        id="region-chat-message"
        className="region-interpretation__question"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        rows={3}
        data-testid="region-chat-message"
        placeholder="Why do you think this is vegetation loss?"
      />

      <button
        type="button"
        className="btn btn--secondary mt-2"
        onClick={() => void handleSend()}
        disabled={loading || message.trim().length === 0}
        data-testid="region-chat-send"
      >
        {loading ? "Sending…" : "Send follow-up"}
      </button>

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
  );
}
