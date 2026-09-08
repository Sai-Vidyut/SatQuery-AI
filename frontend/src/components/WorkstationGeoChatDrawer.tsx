"use client";

import { useEffect, useRef, useState } from "react";
import type { AnalysisResult, EvidenceRegion } from "@/types/domain";
import { RegionGeoChatConversation } from "@/components/RegionGeoChatConversation";
import { SessionGeoChatConversation } from "@/components/SessionGeoChatConversation";
import {
  geoChatCollapseKey,
  resolveGeoChatDrawerMode,
  shouldUseRegionGeoChatApi,
} from "@/lib/geoChatDrawer";

type Props = {
  result: AnalysisResult;
  selectedRegion: EvidenceRegion | null;
  selectedRegionId: string | null;
  chatResetKey: number;
};

export function WorkstationGeoChatDrawer({
  result,
  selectedRegion,
  selectedRegionId,
  chatResetKey,
}: Props) {
  const mode = resolveGeoChatDrawerMode(result);
  const scopeKey = geoChatCollapseKey(chatResetKey, selectedRegionId);
  const [expanded, setExpanded] = useState(false);
  const previousScopeKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (previousScopeKeyRef.current === null) {
      previousScopeKeyRef.current = scopeKey;
      return;
    }
    if (previousScopeKeyRef.current !== scopeKey) {
      setExpanded(false);
      previousScopeKeyRef.current = scopeKey;
    }
  }, [scopeKey]);

  const drawerProps = {
    expanded,
    onExpandedChange: setExpanded,
  };

  if (shouldUseRegionGeoChatApi(result, selectedRegion) && selectedRegion) {
    return (
      <RegionGeoChatConversation
        sessionId={result.session_id}
        result={result}
        selectedRegion={selectedRegion}
        {...drawerProps}
      />
    );
  }

  return (
    <SessionGeoChatConversation
      sessionId={result.session_id}
      result={result}
      mode={mode}
      selectedRegion={selectedRegion}
      selectedRegionId={selectedRegionId}
      chatResetKey={chatResetKey}
      {...drawerProps}
    />
  );
}
