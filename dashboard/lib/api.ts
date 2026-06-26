const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const API_KEY  = process.env.NEXT_PUBLIC_API_KEY  || ""

export async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "X-API-Key": API_KEY }
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export async function apiPost(path: string, body: FormData | object) {
  const isForm = body instanceof FormData
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: isForm ? {"X-API-Key": API_KEY}
                    : {"X-API-Key": API_KEY, "Content-Type": "application/json"},
    body: isForm ? body : JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}
