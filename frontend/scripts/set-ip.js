/**
 * 현재 머신의 로컬 IP를 자동으로 감지해서
 * frontend/.env 와 backend/.env 의 API URL을 업데이트합니다.
 *
 * 사용: node scripts/set-ip.js
 * 또는 npm run dev 에 자동 포함됨
 */

const os = require('os');
const fs = require('fs');
const path = require('path');

// 가상 어댑터가 주로 사용하는 IP 대역 (마지막 옥텟 .1 이 host-only 어댑터 기본값)
const VIRTUAL_RANGES = [
  /^192\.168\.56\./, // VirtualBox Host-Only
  /^192\.168\.57\./, // VirtualBox Host-Only (보조)
  /^192\.168\.64\./, // VMware Fusion
  /^192\.168\.65\./, // VMware Fusion (보조)
  /^172\.17\./,      // Docker 기본 브리지
  /^172\.18\./,      // Docker 커스텀 브리지
  /^172\.19\./,
];

function isVirtualIP(address) {
  return VIRTUAL_RANGES.some((re) => re.test(address));
}

function getLocalIP() {
  const interfaces = os.networkInterfaces();
  const all = [];

  for (const [name, addrs] of Object.entries(interfaces)) {
    for (const addr of addrs) {
      if (addr.family !== 'IPv4' || addr.internal) continue;
      all.push({ name, address: addr.address, virtual: isVirtualIP(addr.address) });
    }
  }

  // 실제 네트워크 어댑터(가상 제외)만 추림
  const real = all.filter((c) => !c.virtual);

  if (real.length > 0) {
    // 10.x 대역 우선 (회사/학교 네트워크에서 흔함)
    const preferred = real.find((c) => c.address.startsWith('10.')) ?? real[0];
    return preferred.address;
  }

  // 실제 어댑터를 못 찾으면 전체에서 10.x 우선
  const fallback = all.find((c) => c.address.startsWith('10.')) ?? all[0];
  return fallback?.address ?? null;
}

function updateEnvFile(filePath, ip) {
  if (!fs.existsSync(filePath)) {
    console.warn(`⚠️  파일 없음: ${filePath}`);
    return;
  }

  let content = fs.readFileSync(filePath, 'utf8');
  const before = content;

  content = content.replace(
    /(EXPO_PUBLIC_API_BASE_URL=http:\/\/)[\d.]+(\:\d+)/g,
    `$1${ip}$2`,
  );
  content = content.replace(
    /(GOOGLE_REDIRECT_URI=http:\/\/)[\d.]+(\:\d+)/g,
    `$1${ip}$2`,
  );

  if (content === before) {
    console.log(`  (변경 없음) ${path.basename(filePath)}`);
  } else {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`  ✅ 업데이트: ${path.basename(filePath)}`);
  }
}

const ip = getLocalIP();

if (!ip) {
  console.error('❌ 로컬 IP를 감지하지 못했습니다. 네트워크 연결을 확인해 주세요.');
  process.exit(1);
}

console.log(`🌐 감지된 IP: ${ip}`);

const root = path.resolve(__dirname, '../..');
updateEnvFile(path.join(root, 'frontend', '.env'), ip);
updateEnvFile(path.join(root, 'backend', '.env'), ip);

console.log('완료! 이제 Expo와 백엔드를 시작하세요.\n');
