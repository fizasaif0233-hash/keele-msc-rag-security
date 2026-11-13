import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Security Evaluation",
  description: "Controlled evaluation of security controls for retrieval-augmented generation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
