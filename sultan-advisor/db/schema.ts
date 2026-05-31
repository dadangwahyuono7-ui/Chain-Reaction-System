import { sqliteTable, text, integer, real } from "drizzle-orm/sqlite-core";

export const user = sqliteTable("user", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  email: text("email").notNull().unique(),
  emailVerified: integer("email_verified", { mode: "boolean" }).notNull().default(false),
  image: text("image"),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(new Date()),
  updatedAt: integer("updated_at", { mode: "timestamp" }).notNull().default(new Date()),
});

export const session = sqliteTable("session", {
  id: text("id").primaryKey(),
  expiresAt: integer("expires_at", { mode: "timestamp" }).notNull(),
  token: text("token").notNull().unique(),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(new Date()),
  updatedAt: integer("updated_at", { mode: "timestamp" }).notNull().default(new Date()),
  ipAddress: text("ip_address"),
  userAgent: text("user_agent"),
  userId: text("user_id").notNull().references(() => user.id, { onDelete: "cascade" }),
});

export const account = sqliteTable("account", {
  id: text("id").primaryKey(),
  accountId: text("account_id").notNull(),
  providerId: text("provider_id").notNull(),
  userId: text("user_id").notNull().references(() => user.id, { onDelete: "cascade" }),
  accessToken: text("access_token"),
  refreshToken: text("refresh_token"),
  idToken: text("id_token"),
  accessTokenExpiresAt: integer("access_token_expires_at", { mode: "timestamp" }),
  refreshTokenExpiresAt: integer("refresh_token_expires_at", { mode: "timestamp" }),
  scope: text("scope"),
  password: text("password"),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(new Date()),
  updatedAt: integer("updated_at", { mode: "timestamp" }).notNull().default(new Date()),
});

export const verification = sqliteTable("verification", {
  id: text("id").primaryKey(),
  identifier: text("identifier").notNull(),
  value: text("value").notNull(),
  expiresAt: integer("expires_at", { mode: "timestamp" }).notNull(),
  createdAt: integer("created_at", { mode: "timestamp" }).default(new Date()),
  updatedAt: integer("updated_at", { mode: "timestamp" }).default(new Date()),
});

export const chatSessions = sqliteTable("chat_sessions", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull().references(() => user.id, { onDelete: "cascade" }),
  title: text("title").notNull().default("Sesi Baru"),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(new Date()),
  updatedAt: integer("updated_at", { mode: "timestamp" }).notNull().default(new Date()),
});

export const messages = sqliteTable("messages", {
  id: text("id").primaryKey(),
  sessionId: text("session_id").notNull().references(() => chatSessions.id, { onDelete: "cascade" }),
  role: text("role").notNull(),
  content: text("content").notNull(),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(new Date()),
});

export const teamMessages = sqliteTable("team_messages", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  userName: text("user_name").notNull(),
  text: text("text").notNull().default(""),
  imageUrl: text("image_url"),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(new Date()),
});

export const marketContext = sqliteTable("market_context", {
  id: text("id").primaryKey(),
  variableName: text("variable_name").notNull().unique(),
  label: text("label").notNull(),
  value: text("value").notNull().default(""),
  updatedAt: integer("updated_at", { mode: "timestamp" }).notNull().default(new Date()),
});

// -- AI Memory System ----------------------------------------------------------
// Stores long-term memories that persist across chat sessions.
// Categories: trade_result, market_insight, pattern, lesson, preference, general
export const memories = sqliteTable("memories", {
  id: text("id").primaryKey(),
  content: text("content").notNull(),
  category: text("category").notNull(), // trade_result | market_insight | pattern | lesson | preference | general
  importance: integer("importance").notNull().default(1), // 1=low, 2=medium, 3=high, 4=critical
  tags: text("tags"), // comma-separated tags for search
  sessionId: text("session_id"), // which chat session created this memory
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().default(new Date()),
});

// -- Paper Trading System ------------------------------------------------------
// Dua akun paper terpisah ("engine" murni doktrin & "ai" diputus AI advisor)
// supaya performa bisa dibandingkan head-to-head tanpa campur tangan Commander.
// Saldo dalam Rupiah (default 10jt). Risk fixed per trade → akuntansi pakai
// R-multiple biar instrument-agnostic (chart apapun: gold/BTC/forex).
export const paperAccounts = sqliteTable("paper_accounts", {
  id: text("id").primaryKey(),                              // "engine" | "ai"
  label: text("label").notNull(),                          // "Engine (Doktrin)" | "AI Advisor"
  initialBalance: real("initial_balance").notNull().default(10_000_000),
  balance: real("balance").notNull().default(10_000_000),  // saldo berjalan (Rupiah)
  riskPerTrade: real("risk_per_trade").notNull().default(100_000), // risk per trade (Rupiah) = 1R
  updatedAt: integer("updated_at", { mode: "timestamp" }).notNull().default(new Date()),
});

export const paperTrades = sqliteTable("paper_trades", {
  id: text("id").primaryKey(),
  accountId: text("account_id").notNull(),                 // "engine" | "ai"
  instrument: text("instrument").notNull(),                // ikut chart aktif (XAUUSD/BTCUSD/dll)
  direction: text("direction").notNull(),                  // BUY | SELL
  setupTf: text("setup_tf"),                               // TF setup (H4/M30/dll)
  grade: text("grade"),                                    // A+/A/B/C
  cfType: text("cf_type"),                                 // LOW | HIGH
  cfCount: integer("cf_count"),                            // CF ke-berapa
  entryPrice: real("entry_price").notNull(),
  slPrice: real("sl_price").notNull(),
  tp1Price: real("tp1_price"),
  tp2Price: real("tp2_price"),
  exitPrice: real("exit_price"),
  status: text("status").notNull().default("OPEN"),        // OPEN | WIN | LOSS | BE
  rMultiple: real("r_multiple"),                           // hasil dalam R (universal)
  pnl: real("pnl"),                                        // hasil Rupiah (rMultiple * riskPerTrade)
  openReason: text("open_reason"),                         // kenapa dibuka (CF fire / AI plan)
  closeReason: text("close_reason"),                       // SL hit / TP1 hit / dll
  openedAt: integer("opened_at", { mode: "timestamp" }).notNull().default(new Date()),
  closedAt: integer("closed_at", { mode: "timestamp" }),
});
