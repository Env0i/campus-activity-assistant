// 导出 logo 资产：无头 Edge 透明背景栅格化 → 裁切 → PNG / ICO。
// 用法（仓库根）：node design/brand/tools/export.js
// Edge 不在默认位置时用环境变量 EDGE_PATH 指定；中间文件写系统临时目录，不落进仓库。
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const kit = require('./pngkit');

const brand = path.resolve(__dirname, '..');
const svg = (n) => 'file:///' + path.join(brand, 'svg', n).replace(/\\/g, '/');
const work = path.join(os.tmpdir(), 'campus-brand-export');
fs.mkdirSync(work, { recursive: true });
const edge = process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';

// 每张拼板：画布大小 + 一组 {输出名, 源 svg, 宽, 高, x, y}
const sheets = [
  { id: 'a', w: 1560, h: 1030, items: [
    ['logo-1024', 'logo.svg', 1024, 1024, 0, 0],
    ['logo-512', 'logo.svg', 512, 512, 1040, 0],
    ['maskable-512', 'logo-tile-square.svg', 512, 512, 1040, 516]] },
  { id: 'b', w: 1640, h: 530, items: [
    ['tile-512', 'logo-tile.svg', 512, 512, 0, 0],
    ['tile-192', 'logo-tile.svg', 192, 192, 520, 0],
    ['apple-touch-icon', 'logo-tile-square.svg', 180, 180, 520, 200],
    ['logo-256', 'logo.svg', 256, 256, 720, 0],
    ['logo-128', 'logo.svg', 128, 128, 984, 0],
    ['logo-64', 'logo.svg', 64, 64, 1120, 0],
    ['logo-48', 'logo.svg', 48, 48, 1192, 0],
    ['logo-40', 'logo.svg', 40, 40, 1248, 0],
    ['logo-32', 'logo-small.svg', 32, 32, 1296, 0],
    ['logo-24', 'logo-small.svg', 24, 24, 1336, 0],
    ['logo-20', 'logo-small.svg', 20, 20, 1368, 0],
    ['logo-16', 'logo-small.svg', 16, 16, 1396, 0]] },
  { id: 'c', w: 1040, h: 370, items: [
    ['lockup', 'lockup.svg', 500, 112, 0, 0],
    ['lockup-dark', 'lockup-dark.svg', 500, 112, 520, 0],
    ['lockup@2x', 'lockup.svg', 1000, 224, 0, 130]] },
  { id: 'd', w: 1040, h: 240, items: [
    ['lockup-dark@2x', 'lockup-dark.svg', 1000, 224, 0, 0]] }
];

const out = {};
for (const sh of sheets) {
  const html = '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:transparent}img{position:absolute;display:block}</style>' +
    sh.items.map((it) => `<img src="${svg(it[1])}" width="${it[2]}" height="${it[3]}" style="left:${it[4]}px;top:${it[5]}px">`).join('');
  const page = path.join(work, 'sheet-' + sh.id + '.html'), shot = path.join(work, 'sheet-' + sh.id + '.png');
  fs.writeFileSync(page, html);
  if (fs.existsSync(shot)) fs.unlinkSync(shot);
  const r = spawnSync(edge, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--force-device-scale-factor=1',
    '--default-background-color=00000000', '--user-data-dir=' + path.join(work, 'edge-profile-' + sh.id), '--window-size=' + sh.w + ',' + sh.h,
    '--virtual-time-budget=3000', '--screenshot=' + shot, 'file:///' + page.replace(/\\/g, '/')], { timeout: 60000 });
  if (!fs.existsSync(shot)) throw new Error('screenshot failed for sheet ' + sh.id + ': ' + (r.stderr || '').toString().slice(0, 300));
  const img = kit.decode(fs.readFileSync(shot));
  if (img.w !== sh.w || img.h !== sh.h) throw new Error('sheet ' + sh.id + ' size ' + img.w + 'x' + img.h);
  for (const it of sh.items) out[it[0]] = kit.crop(img, it[4], it[5], it[2], it[3]);
}

// 透明检查：拼板角落必须是全透明，否则说明背景没去掉
for (const k of Object.keys(out)) {
  const im = out[k];
  if (k.startsWith('maskable') || k.startsWith('apple') || k.startsWith('tile')) continue;
  if (im.data[3] !== 0) throw new Error(k + ': top-left pixel not transparent');
}
for (const [k, im] of Object.entries(out)) fs.writeFileSync(path.join(brand, 'png', k + '.png'), kit.encode(im));
fs.writeFileSync(path.join(brand, 'ico', 'app.ico'), kit.ico([16, 20, 24, 32, 40, 48, 64, 256].map((n) => out['logo-' + n])));
fs.writeFileSync(path.join(brand, 'ico', 'favicon.ico'), kit.ico([16, 32, 48].map((n) => out['logo-' + n])));
console.log('png: ' + Object.keys(out).length + ', ico: app.ico favicon.ico');
