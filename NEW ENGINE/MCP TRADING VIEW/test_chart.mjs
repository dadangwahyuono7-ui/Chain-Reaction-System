import CDP from 'chrome-remote-interface';

const list = await CDP.List({ port: 9222 });
const chartTab = list.find(t => t.url && t.url.includes('tradingview.com/chart'));
if (!chartTab) { console.log('Chart tab not found'); process.exit(1); }
console.log('Chart tab found:', chartTab.title);

const client = await CDP({ target: chartTab.id, port: 9222 });
const { Runtime } = client;
await Runtime.enable();

const result = await Runtime.evaluate({
  expression: `(function() {
    try {
      var chart = window.TradingViewApi._activeChartWidgetWV.value();
      return JSON.stringify({
        symbol: chart.symbol(),
        resolution: chart.resolution(),
        chartType: chart.chartType(),
        studies: chart.getAllStudies().map(s => s.name)
      });
    } catch(e) {
      return JSON.stringify({ error: e.message });
    }
  })()`,
  returnByValue: true
});

console.log(JSON.parse(result.result.value));
await client.close();
