/** @type {import('next').NextConfig} */
const nextConfig = {
  // 把前端 /api/* 请求代理到后端 FastAPI（本地 8000 端口），避免跨域
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://127.0.0.1:8000/:path*' },
    ];
  },
};

export default nextConfig;
