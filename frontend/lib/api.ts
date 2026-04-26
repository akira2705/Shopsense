const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatMessage {
  role: "user" | "agent";
  content: string;
  type?: "text" | "recommendation";
  recommendation?: RecommendationData;
}

export interface ConfidenceBreakdown {
  category: number;
  budget: number;
  use_case: number;
  priorities: number;
  ambiguity_penalty: number;
}

export interface ConfidenceState {
  score: number;
  breakdown: ConfidenceBreakdown;
  journey: { label: string; score: number }[];
}

export interface EliminatedProduct {
  title: string;
  price: number;
  reason: string;
}

export interface RecommendationData {
  product: {
    id: string;
    title: string;
    price: number;
    image_url: string | null;
    variant_id: string | null;
    tags: string[];
    source?: string;       // "amazon" | "flipkart" | "carwale" | "olx"
    rating?: number | null;
    review_count?: number | null;
  };
  reasoning: string;
  regret_risk: "low" | "medium" | "high";
  regret_scenario: string;
  tradeoff: string;
  confidence_score: number;
  elimination: EliminatedProduct[];
}

export interface SSEEvent {
  type:
    | "confidence"
    | "message"
    | "followup"
    | "recommendation"        // legacy — kept for fallback
    | "recommendation_start"  // A: product + elimination, no reasoning yet
    | "token"                 // A: streaming reasoning chunk
    | "recommendation_done"   // A: regret_risk / tradeoff after stream ends
    | "error"
    | "done";
  // confidence
  score?: number;
  breakdown?: ConfidenceBreakdown;
  session_id?: string;
  // message / followup
  content?: string;
  question?: string;
  message?: string;
  // token (A)
  text?: string;
  // recommendation fields (legacy + recommendation_start + recommendation_done)
  product?: RecommendationData["product"];
  reasoning?: string;
  regret_risk?: "low" | "medium" | "high";
  regret_scenario?: string;
  tradeoff?: string;
  confidence_score?: number;
  elimination?: EliminatedProduct[];
}

export async function* streamChat(
  message: string,
  sessionId: string,
  history: ChatMessage[]
): AsyncGenerator<SSEEvent> {
  const historyPayload = history.map((m) => ({
    role: m.role,
    content: m.content,
  }));

  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      history: historyPayload,
    }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        try {
          const event: SSEEvent = JSON.parse(jsonStr);
          yield event;
        } catch {
          // skip malformed line
        }
      }
    }
  }
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_URL}/api/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  }).catch(() => {});
}
