import type { NextConfig } from "next";

// 로그인 뒤 화면(소개 / · /privacy · /terms 밖의 모든 화면 주소)은 검색에서 뺀다.
// 점이 든 주소(그림 · manifest · sw.js · robots.txt 같은 파일)와 /_next 는 그대로 둔다(공유 미리보기 그림이 막히지 않게).
const config: NextConfig = {
  async headers() {
    return [{ source: "/((?!privacy$|terms$|_next/)[^.]+)", headers: [{ key: "X-Robots-Tag", value: "noindex" }] }];
  },
};

export default config;
