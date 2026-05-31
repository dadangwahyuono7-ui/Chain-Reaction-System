import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { nanoid } from "nanoid";
import { writeFile, mkdir, copyFile } from "fs/promises";
import { existsSync } from "fs";
import path from "path";

export const dynamic = "force-dynamic";

const ASISTEN_DIR = "D:\\PROJECT TRADING\\asisten dadang\\uploads";
const PUBLIC_DIR  = path.join(process.cwd(), "public", "uploads");

// File types yang diizinkan
const ALLOWED_TYPES: Record<string, { ext: string; kind: "image" | "file" }> = {
  "image/jpeg":       { ext: "jpg",  kind: "image" },
  "image/png":        { ext: "png",  kind: "image" },
  "image/webp":       { ext: "webp", kind: "image" },
  "image/gif":        { ext: "gif",  kind: "image" },
  "application/pdf":  { ext: "pdf",  kind: "file"  },
  "text/plain":       { ext: "txt",  kind: "file"  },
  "text/csv":         { ext: "csv",  kind: "file"  },
  "application/json": { ext: "json", kind: "file"  },
};

const MAX_BYTES = 15 * 1024 * 1024; // 15MB

export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const form = await req.formData();
  const file = form.get("file");
  if (!(file instanceof File)) {
    return Response.json({ error: "File tidak ada" }, { status: 400 });
  }

  const meta = ALLOWED_TYPES[file.type];
  if (!meta) {
    return Response.json({
      error: "Tipe file tidak didukung. Boleh: gambar (jpg/png/webp), PDF, txt, csv, json"
    }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return Response.json({ error: "File terlalu besar (max 15MB)" }, { status: 400 });
  }

  const buf   = Buffer.from(await file.arrayBuffer());
  const ts    = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const fname = `${ts}-${nanoid(6)}.${meta.ext}`;

  // 1. Simpan ke asisten dadang\uploads\
  await mkdir(ASISTEN_DIR, { recursive: true });
  await writeFile(path.join(ASISTEN_DIR, fname), buf);

  // 2. Copy ke public/uploads biar bisa ditampilkan di browser
  await mkdir(PUBLIC_DIR, { recursive: true });
  await writeFile(path.join(PUBLIC_DIR, fname), buf);

  // 3. Untuk gambar: balikin juga base64 biar AI bisa baca kontennya
  const url = `/uploads/${fname}`;
  if (meta.kind === "image") {
    const base64 = buf.toString("base64");
    return Response.json({ url, base64, mimeType: file.type, kind: "image", name: file.name, size: file.size });
  }

  // 4. Untuk file teks/PDF: balikin URL saja (AI bisa baca via read_file)
  const savedPath = path.join(ASISTEN_DIR, fname);
  return Response.json({ url, kind: "file", name: file.name, size: file.size, savedPath });
}
