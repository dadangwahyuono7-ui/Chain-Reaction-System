//+------------------------------------------------------------------+
//| DD_PanelPreview.mq5 - BOLD TEXT A/B TEST                         |
//| Dadang: "masih sama, lo coba buat ulang aja di mockup" - moving   |
//| all further bold-text experiments back here instead of burning    |
//| production compile/deploy cycles. Draws 6 techniques stacked      |
//| vertically, each with the SAME sample text ("11620.40 / 10747.02"|
//| - the exact string he boxed in red) so they can be compared       |
//| directly, side by side, in one screenshot. Whichever letter looks |
//| genuinely solid/bold is the one that goes into production.        |
//+------------------------------------------------------------------+
#property strict
#include <Canvas\Canvas.mqh>

#define PV_NAME "DD_PREVIEW_CANVAS"
#define SAMPLE "11620.40 / 10747.02"

CCanvas canvas;
color WHITE_C = C'255,255,255';
color GOLD    = C'217,180,101';
color SILVER  = C'139,149,167';
color BG_C    = C'14,16,23';

int PX = 290, PY = 18, PW = 420, PH = 300;

void Label(int x, int y, string s)
{
   canvas.FontSet("Arial", 9, 400);
   canvas.TextOut(x, y, s, ColorToARGB(GOLD, 255), TA_LEFT | TA_TOP);
}

void DrawPreviewPanel()
{
   canvas.CreateBitmapLabel(PV_NAME, PX - 10, PY - 10, PW, PH, COLOR_FORMAT_ARGB_NORMALIZE);
   ObjectSetInteger(0, PV_NAME, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   canvas.Erase(0);
   canvas.FillRectangle(0, 0, PW, PH, ColorToARGB(BG_C, 255));
   canvas.FillRectangle(0, 0, PW, 2, ColorToARGB(GOLD, 255));

   int x = 16, y = 14;
   uint argbWhite = ColorToARGB(WHITE_C, 255);

   // A - baseline: regular weight, single draw, size 12
   Label(x, y, "A) regular, weight=400, size 12"); y += 14;
   canvas.FontSet("Arial", 12, 400);
   canvas.TextOut(x, y, SAMPLE, argbWhite, TA_LEFT | TA_TOP); y += 26;

   // B - weight flag only
   Label(x, y, "B) weight=700 flag only, size 12"); y += 14;
   canvas.FontSet("Arial", 12, 700);
   canvas.TextOut(x, y, SAMPLE, argbWhite, TA_LEFT | TA_TOP); y += 26;

   // C - weight flag + 2-way diagonal stamp (current production attempt)
   Label(x, y, "C) weight=700 + 2x diagonal stamp"); y += 14;
   canvas.FontSet("Arial", 12, 700);
   canvas.TextOut(x,     y,     SAMPLE, argbWhite, TA_LEFT | TA_TOP);
   canvas.TextOut(x + 1, y + 1, SAMPLE, argbWhite, TA_LEFT | TA_TOP); y += 26;

   // D - 8-direction stamp (heavier), regular weight
   Label(x, y, "D) 8-direction stamp (N/S/E/W/diag), weight=400"); y += 14;
   canvas.FontSet("Arial", 12, 400);
   for(int dx = -1; dx <= 1; dx++)
      for(int dy = -1; dy <= 1; dy++)
         canvas.TextOut(x + dx, y + dy, SAMPLE, argbWhite, TA_LEFT | TA_TOP);
   y += 26;

   // E - dark outline behind white fill (classic "outlined text" trick -
   // draws a near-black copy in a ring around the glyph first, then the
   // white text on top - increases apparent weight via contrast/silhouette
   // rather than depending on any font-weight API working at all).
   Label(x, y, "E) black outline + white fill, weight=700"); y += 14;
   canvas.FontSet("Arial", 12, 700);
   uint argbOutline = ColorToARGB(C'0,0,0', 255);
   for(int dx = -1; dx <= 1; dx++)
      for(int dy = -1; dy <= 1; dy++)
         if(dx != 0 || dy != 0)
            canvas.TextOut(x + dx, y + dy, SAMPLE, argbOutline, TA_LEFT | TA_TOP);
   canvas.TextOut(x, y, SAMPLE, argbWhite, TA_LEFT | TA_TOP); y += 26;

   // F - size-only control (no stamping, no weight trick, just bigger)
   Label(x, y, "F) size-only, size 17, weight=400"); y += 14;
   canvas.FontSet("Arial", 17, 400);
   canvas.TextOut(x, y, SAMPLE, argbWhite, TA_LEFT | TA_TOP); y += 30;

   canvas.Update();
   Print("DD_PanelPreview (bold A/B test): 6 techniques drawn, compare A-F. Remove this EA from the chart to clear it.");
}

int OnInit() { DrawPreviewPanel(); return(INIT_SUCCEEDED); }
void OnDeinit(const int reason) { canvas.Destroy(); ChartRedraw(0); }
void OnTick() {}
