import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quant Sports Trading",
  description: "Evidence-first quantitative sports trading dashboard"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
