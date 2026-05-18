import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AnimaShorts AI — Video Shorts Generator",
  description: "Upload your images, write your prompt — get a cinematic vertical short with AI narration in minutes",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "AnimaShorts",
    startupImage: [
      { url: "/splash-1290x2796.png", media: "(device-width: 430px) and (device-height: 932px) and (-webkit-device-pixel-ratio: 3)" },
      { url: "/splash-1179x2556.png", media: "(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3)" },
      { url: "/splash-1170x2532.png", media: "(device-width: 390px) and (device-height: 844px) and (-webkit-device-pixel-ratio: 3)" },
      { url: "/splash-750x1334.png",  media: "(device-width: 375px) and (device-height: 667px) and (-webkit-device-pixel-ratio: 2)" },
      { url: "/splash-1488x2266.png", media: "(device-width: 744px) and (device-height: 1133px) and (-webkit-device-pixel-ratio: 2)" },
    ],
  },
  icons: {
    icon: "/icon-192.png",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "AnimaShorts AI",
    description: "AI-powered vertical video generator",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0891B2",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ocean-dark antialiased">
        {children}
        <script dangerouslySetInnerHTML={{ __html: `
          if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
              navigator.serviceWorker.register('/sw.js').catch(() => {});
            });
            // When a new SW activates it sends SW_RELOAD → reload page for fresh chunks
            navigator.serviceWorker.addEventListener('message', function(e) {
              if (e.data && e.data.type === 'SW_RELOAD') {
                window.location.reload();
              }
            });
          }
        `}} />
      </body>
    </html>
  );
}
