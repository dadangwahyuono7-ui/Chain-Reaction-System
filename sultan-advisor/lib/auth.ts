import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { db } from "@/db";
import * as schema from "@/db/schema";

export const auth = betterAuth({
  database: drizzleAdapter(db, { provider: "sqlite", schema }),
  emailAndPassword: { enabled: true },
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: process.env.BETTER_AUTH_URL,
  // Origin yang diizinkan login. localhost untuk lokal, *.trycloudflare.com untuk
  // share via Cloudflare Tunnel ke team. EXTRA_TRUSTED_ORIGINS (comma-separated)
  // bisa diisi di .env.local kalau pakai domain/tunnel custom.
  trustedOrigins: [
    "http://localhost:3002",
    "https://*.trycloudflare.com",
    ...(process.env.EXTRA_TRUSTED_ORIGINS?.split(",").map(s => s.trim()).filter(Boolean) ?? []),
  ],
});
