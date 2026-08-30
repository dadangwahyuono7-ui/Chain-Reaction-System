#property script_show_inputs false
#property strict
void OnStart()
{
   int total = ObjectsTotal(0);
   Print("=== NUKE: Hapus ", total, " objek...");
   ObjectsDeleteAll(0);
   ChartRedraw(0);
   Print("=== NUKE: Chart bersih!");
   Alert("Chart bersih! Semua garis dihapus.");
}
