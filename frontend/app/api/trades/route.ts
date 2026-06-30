import { NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_BASE ?? process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(`${API_BASE}/paper-trades`, { cache: "no-store" });
    if (!response.ok) {
      return NextResponse.json([], { status: 200 });
    }
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json([], { status: 200 });
  }
}
