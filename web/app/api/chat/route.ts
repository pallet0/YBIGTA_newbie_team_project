// app/api/chat/route.ts
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

type ToolArgs = Record<string, string | number>;
type GeminiContent = {
  role: string;
  parts: Array<{
    text?: string;
    functionCall?: { name: string; args: ToolArgs };
    functionResponse?: { name: string; response: unknown };
    thoughtSignature?: string;
  }>;
};

// ============================================================
// MCP 클라이언트 연결
// ============================================================
async function getMcpClient() {
  const transport = new StreamableHTTPClientTransport(
    new URL(process.env.MCP_SERVER_URL!),
    {
      requestInit: {
        headers: {
          Authorization: `Bearer ${process.env.MCP_AUTH_TOKEN}`,
        },
      },
    }
  );
  const client = new Client({ name: "ybigta-agent", version: "1.0.0" });
  await client.connect(transport);
  return client;
}

// ============================================================
// 실제 MCP 서버가 제공하는 tool 3개 (C의 server.py 기준)
// ============================================================
const toolDeclarations = [
  {
    name: "get_latest_data",
    description: "가장 최근에 수집된 리뷰를 조회한다",
    parameters: {
      type: "OBJECT",
      properties: {
        limit: { type: "NUMBER", description: "가져올 개수 (기본 10)" },
      },
    },
  },
  {
    name: "search_data",
    description: "키워드와 기간으로 리뷰를 검색한다",
    parameters: {
      type: "OBJECT",
      properties: {
        keyword: { type: "STRING", description: "검색 키워드" },
        start_date: { type: "STRING", description: "검색 시작일 (YYYY-MM-DD)" },
        end_date: { type: "STRING", description: "검색 종료일 (YYYY-MM-DD)" },
        limit: { type: "NUMBER", description: "가져올 개수 (기본 10)" },
      },
    },
  },
  {
    name: "get_statistics",
    description: "리뷰 별점(또는 지정 컬럼)의 평균, 최솟값, 최댓값, 개수를 조회한다",
    parameters: {
      type: "OBJECT",
      properties: {
        column: { type: "STRING", description: "통계 낼 컬럼명 (기본 rating)" },
      },
    },
  },
];

// ============================================================
// MCP 서버에 실제로 tool 호출
// ============================================================
async function callTool(name: string, args: ToolArgs) {
    console.log(`[Tool Call] ${name}`, args);
    try {
      const client = await getMcpClient();
      try {
        const result = await client.callTool({ name, arguments: args });
        return result;
      } finally {
        await client.close();
      }
    } catch (err) {
      console.error(`[Tool Error] ${name}`, err);
      return { error: "데이터 조회 중 오류가 발생했습니다." };
    }
  }

// ============================================================
// Gemini 호출
// ============================================================
async function callGemini(contents: GeminiContent[]) {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=${process.env.GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contents,
        tools: [{ functionDeclarations: toolDeclarations }],
      }),
    }
  );
  return res.json();
}

// ============================================================
// 메인 로직
// ============================================================
export async function POST(req: Request) {
  const { question } = await req.json();

  const contents: GeminiContent[] = [{ role: "user", parts: [{ text: question }] }];
  let json = await callGemini(contents);

  const toolCalls: { name: string; args: ToolArgs; result: unknown }[] = [];

  for (let i = 0; i < 5; i++) {
    const part = json.candidates?.[0]?.content?.parts?.[0];

    if (!part?.functionCall) break;

    const { name, args } = part.functionCall;
    const toolResult = await callTool(name, args);

    toolCalls.push({ name, args, result: toolResult });

    contents.push({ role: "model", parts: [part] });
    contents.push({
      role: "user",
      parts: [{ functionResponse: { name, response: toolResult as object } }],
    });

    json = await callGemini(contents);
  }

  const answer = json.candidates?.[0]?.content?.parts?.[0]?.text ?? "응답 실패";

  return Response.json({ answer, toolCalls });
}