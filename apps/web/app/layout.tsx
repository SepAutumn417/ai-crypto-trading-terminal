'use client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import './globals.css';
import { Navbar } from '@/components/layout/Navbar';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient());
  return (
    <html lang="zh">
      <body>
        <QueryClientProvider client={client}>
          <Navbar />
          <main className="container mx-auto px-4 py-6">{children}</main>
        </QueryClientProvider>
      </body>
    </html>
  );
}