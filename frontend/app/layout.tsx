import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'FinAlly — AI Trading Workstation',
  description: 'Bloomberg-feel AI trading workstation with simulated portfolio and LLM copilot.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen font-sans antialiased text-[13px] leading-tight">
        {children}
      </body>
    </html>
  );
}
