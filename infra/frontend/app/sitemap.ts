// sitemap.xml: 로그인 없이 보이는 소개 · 개인정보처리방침만.
import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/privacy"].map((p) => ({ url: SITE + p }));
}
