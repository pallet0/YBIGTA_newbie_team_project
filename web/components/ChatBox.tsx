"use client";
import { useState, useRef, useEffect } from "react";

type ToolCall = { name: string; args: Record<string, string>; result: unknown };
type Message = { role: string; text: string; toolCalls?: ToolCall[] };

export default function ChatBox() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    if (!question.trim() || loading) return;

    const userMsg = question;
    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setQuestion("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: userMsg }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: data.answer, toolCalls: data.toolCalls },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: "오류가 발생했습니다. 다시 시도해주세요." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-[640px] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
      {/* 헤더 */}
      <div className="flex items-center gap-3 border-b border-slate-100 bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-400/20 text-lg">
          📊
        </div>
        <div>
          <h1 className="text-sm font-semibold text-white">Data Analysis Agent</h1>
          <p className="text-xs text-slate-400">실시간 데이터 기반 분석</p>
        </div>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50 px-5 py-6">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
            <div className="mb-3 text-3xl">💬</div>
            <p className="text-sm">궁금한 데이터를 물어보세요</p>
            <p className="mt-1 text-xs text-slate-300">
                예: &quot;최근 리뷰 평점 평균이 어때?&quot;
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex flex-col ${
              m.role === "user" ? "items-end" : "items-start"
            }`}
          >
            {/* Tool 호출 정보 */}
            {m.role === "agent" && m.toolCalls && m.toolCalls.length > 0 && (
              <div className="mb-2 max-w-[85%] space-y-1.5">
                {m.toolCalls.map((tc, j) => (
                  <details
                    key={j}
                    className="group rounded-lg border border-indigo-100 bg-indigo-50/70 px-3 py-2 text-xs text-indigo-700 open:bg-indigo-50"
                  >
                    <summary className="flex cursor-pointer list-none items-center gap-1.5 font-medium">
                      <span className="text-indigo-400">▸</span>
                      <span>🔧 MCP Tool: {tc.name}</span>
                      <span className="text-indigo-400">
                        ({JSON.stringify(tc.args)})
                      </span>
                    </summary>
                    <pre className="mt-2 overflow-x-auto rounded-md bg-white/80 p-2 text-[11px] leading-relaxed text-slate-600">
                      {JSON.stringify(tc.result, null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            )}

            {/* 말풍선 */}
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[13.5px] leading-relaxed shadow-sm ${
                m.role === "user"
                  ? "rounded-br-sm bg-slate-900 text-white"
                  : "rounded-bl-sm border border-slate-200 bg-white text-slate-800"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-slate-400 shadow-sm w-fit">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 입력 영역 */}
      <div className="flex items-center gap-2 border-t border-slate-100 bg-white p-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="질문을 입력하세요..."
          disabled={loading}
          className="flex-1 rounded-full border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:bg-white disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={loading || !question.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="h-4 w-4"
          >
            <path d="M3.4 20.4l17.45-8.4a1 1 0 000-1.8L3.4 1.8a1 1 0 00-1.4 1.1l1.6 7.1 8.1.9-8.1.9-1.6 7.1a1 1 0 001.4 1.5z" />
          </svg>
        </button>
      </div>
    </div>
  );
}