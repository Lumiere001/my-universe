// robots.txt: 검색에는 소개(/) · /privacy · /terms 만 내놓는다(sitemap.xml). 로그인 뒤 화면은 막지 않고
// next.config.ts 가 X-Robots-Tag: noindex 로 뺀다(막으면 noindex 를 읽지 못해 주소만 색인될 수 있음).
import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: "/" }, sitemap: `${SITE}/sitemap.xml` };
}
