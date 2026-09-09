import './globals.css';

export const metadata = {
  title: '数据分析 Agent',
  description: '用自然语言查询、分析数据',
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
