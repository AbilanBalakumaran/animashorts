import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AnimaShorts AI — Anime Shorts Generator",
  description: "Turn any idea into a cinematic anime-style TikTok short in seconds",
  openGraph: {
    title: "AnimaShorts AI",
    description: "AI-powered anime short video generator",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ocean-dark antialiased">{children}</body>
    </html>
  );
}
