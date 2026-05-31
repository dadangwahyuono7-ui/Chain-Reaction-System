// Test terminal capabilities
const W = process.stdout.columns || 80;
const K = {
  x:'\x1b[0m', b:'\x1b[1m', d:'\x1b[2m',
  gr:'\x1b[92m', rd:'\x1b[91m', yw:'\x1b[93m',
  cy:'\x1b[96m', mg:'\x1b[95m', wh:'\x1b[97m', gy:'\x1b[90m',
};

process.stdout.write('\x1b[2J\x1b[H'); // clear

const lines = [
  `Terminal width: ${W} cols`,
  ``,
  `COLOR TEST:`,
  `${K.gr}GREEN${K.x}  ${K.rd}RED${K.x}  ${K.yw}YELLOW${K.x}  ${K.cy}CYAN${K.x}  ${K.mg}MAGENTA${K.x}  ${K.wh}WHITE${K.x}  ${K.gy}GRAY${K.x}`,
  `${K.gr}${K.b}BOLD GREEN${K.x}  ${K.rd}${K.b}BOLD RED${K.x}  ${K.gy}${K.d}DIM GRAY${K.x}`,
  ``,
  `BOX DRAWING TEST:`,
  `╔${'═'.repeat(W-2)}╗`,
  `║ ${'BOX LINE'.padEnd(W-3)}║`,
  `╠${'═'.repeat(W-2)}╣`,
  `║ ${K.gr}GREEN TEXT IN BOX${K.x}${' '.repeat(W-20)}║`,
  `║ ${K.rd}RED TEXT IN BOX  ${K.x}${' '.repeat(W-20)}║`,
  `╚${'═'.repeat(W-2)}╝`,
  ``,
  `ANIMATION (will pulse 5x):`,
];
process.stdout.write(lines.join('\n') + '\n');

// Pulse test
let f = 0;
const t = setInterval(() => {
  process.stdout.write(`\x1b[14;1H`); // go to line 14
  const c = f%2===0 ? K.gr+K.b : K.yw+K.b;
  process.stdout.write(`${c}  >> PULSE TEST << ${f}  ${K.x}\n`);
  f++;
  if(f>=10){ clearInterval(t); process.stdout.write(`\n${K.cy}DONE. Terminal width=${W}${K.x}\n`); }
}, 300);
