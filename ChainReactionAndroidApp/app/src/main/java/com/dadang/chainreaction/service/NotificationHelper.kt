package com.dadang.chainreaction.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import androidx.core.app.NotificationCompat
import com.dadang.chainreaction.MainActivity
import com.dadang.chainreaction.R
import com.dadang.chainreaction.data.model.CalendarEvent
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.util.Formatters

class NotificationHelper(private val context: Context) {

    private val notificationManager =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    private val prefs = NotificationPreferences.getInstance(context)

    // State memory to detect state transitions across all timeframes
    private val lastTfDirections = mutableMapOf<String, String>()
    private var lastM5Status: String? = null
    private var lastAction: String? = null
    private var lastChainLayer: Int? = null
    private var lastWallSweepActive: Boolean = false
    private var lastSupplyBreakState: String? = null
    private var lastDemandBreakState: String? = null
    private val notifiedNewsNames = mutableSetOf<String>()
    private var lastConfluenceAlertDir: String? = null
    private var lastConfluenceAlertTime: Long = 0L
    private var lastTouchedZone: String? = null
    private var lastTouchedZoneTime: Long = 0L
    private var lastMegaWallNotified: String? = null

    init {
        createAlertChannel()
    }

    private fun createAlertChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            val audioAttributes = AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT)
                .build()

            val channel = NotificationChannel(
                CHANNEL_ALERTS,
                "Trading Signal Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "High-priority breakout & regime flip signals across all timeframes, Action, Chain, and Wall Sweeps"
                enableLights(true)
                enableVibration(true)
                setSound(soundUri, audioAttributes)
            }
            notificationManager.createNotificationChannel(channel)
        }
    }

    fun checkAndNotify(status: SultanStatus, calendarEvents: List<CalendarEvent>) {
        if (!prefs.isNotificationsEnabled) return

        val priceStr = "$" + Formatters.formatPrice(status.price)

        // 1. Check Multi-Timeframe Breakout & Regime Flips (D1, H4, H1, M30, M15, M5)
        val tfMap = listOf(
            Triple("D1", status.regime.d1, NOTIF_ID_D1_FLIP),
            Triple("H4", status.regime.h4, NOTIF_ID_H4_FLIP),
            Triple("H1", status.regime.h1, NOTIF_ID_H1_FLIP),
            Triple("M30", status.regime.m30, NOTIF_ID_M30_FLIP),
            Triple("M15", status.regime.m15, NOTIF_ID_M15_FLIP),
            Triple("M5", status.regime.m5, NOTIF_ID_M5_FLIP)
        )

        tfMap.forEach { (tf, currentDir, notifId) ->
            val lastDir = lastTfDirections[tf]
            if (lastDir != null && currentDir.isNotBlank() && currentDir != "WAIT" && currentDir != "UNKNOWN") {
                if (currentDir != lastDir) {
                    if (prefs.isTfFlipEnabled(tf)) {
                        val emoji = if (currentDir.contains("BUY", ignoreCase = true)) "🟢" else "🔴"
                        val title = "$emoji $tf FLIP: $currentDir"
                        val msg = "Harga $priceStr • $tf Bias Berubah ke $currentDir • HTF Bias: ${status.regime.htfBias} • Alignment: ${Formatters.formatPercent(status.regime.alignmentPct)}"
                        sendAlert(notifId, title, msg)
                    }
                }
            }
            lastTfDirections[tf] = currentDir
        }

        // Check M5 specific WITH_TREND confirmation transition
        val currentM5Status = status.regime.m5Status
        if (lastM5Status != null && currentM5Status == "WITH_TREND" && lastM5Status != "WITH_TREND") {
            if (prefs.isM5FlipEnabled) {
                val title = "⚡ M5 WITH TREND CONFIRMED (${status.regime.m5})"
                val msg = "Harga $priceStr • Momentum: ${status.signals.momentumM5?.text ?: "-"} • Bias: ${status.regime.htfBias}"
                sendAlert(NOTIF_ID_M5_CF, title, msg)
            }
        }
        lastM5Status = currentM5Status

        // 2. Check Action Change (e.g. WAIT -> BUY_PULLBACK)
        val currentAction = status.context.action
        if (lastAction != null && currentAction != lastAction && currentAction != "WAIT_OBSERVE") {
            if (prefs.isActionChangeEnabled) {
                val emoji = if (currentAction.contains("BUY")) "🟢" else if (currentAction.contains("SELL")) "🔴" else "⚡"
                val title = "$emoji ACTION SIGNAL: ${currentAction.replace("_", " ")}"
                val msg = "Harga $priceStr • Conviction: ${status.conviction.score}/${status.conviction.max} (${status.conviction.grade}) • HTF: ${status.regime.htfBias}"
                sendAlert(NOTIF_ID_ACTION, title, msg)
            }
        }
        lastAction = currentAction

        // 3. Check Chain Signal Layer Upgrade (e.g. Layer 0 -> Layer 1/2/3)
        val currentChain = status.signals.chainSignal
        val currentLayer = currentChain?.layer ?: 0
        if (lastChainLayer != null && currentLayer > (lastChainLayer ?: 0) && currentLayer >= 1) {
            if (prefs.isChainUpgradeEnabled) {
                val dir = currentChain?.dir ?: ""
                val emoji = if (dir.contains("BUY")) "🟢" else "🔴"
                val title = "$emoji CHAIN REACTION LAYER $currentLayer ($dir)"
                val msg = "Harga $priceStr • Momentum: ${status.signals.momentumM5?.text ?: "-"} • Flow: ${status.flow.flowDominant}"
                sendAlert(NOTIF_ID_CHAIN, title, msg)
            }
        }
        lastChainLayer = currentLayer

        // 4. Check Wall Sweep Alert
        val sweep = status.wallSweep
        if (sweep.active && !lastWallSweepActive) {
            if (prefs.isWallSweepEnabled) {
                val side = sweep.side.uppercase()
                val emoji = if (side == "ASK") "🟢" else "🔴"
                val title = "$emoji BOOKMAP WALL SWEEP ($side)"
                val msg = "Harga $priceStr • Likuiditas ${sweep.size.toInt()} Lot di $${Formatters.formatPrice(sweep.price)} Berhasil Disapu!"
                sendAlert(NOTIF_ID_SWEEP, title, msg)
            }
        }
        lastWallSweepActive = sweep.active

        // 5. Check High-Impact News Alerts (mins_until <= 15)
        if (prefs.isHighImpactNewsEnabled) {
            calendarEvents.filter { it.impact.equals("high", ignoreCase = true) && it.minsUntil in 1..15 }.forEach { event ->
                if (!notifiedNewsNames.contains(event.name)) {
                    notifiedNewsNames.add(event.name)
                    val title = "🚨 HIGH-IMPACT NEWS SEBENTAR LAGI (${event.minsUntil}m)"
                    val msg = "${event.name} [${event.country}] • Pukul ${event.time} • Waspadai volatilitas ekstrem!"
                    sendAlert(NOTIF_ID_NEWS, title, msg)
                }
            }
        }

        // 6. Check S&D Break State Confirmations
        val sdBreak = status.sdZones?.breakStatus
        if (sdBreak != null) {
            val currSupplyState = sdBreak.supplyState
            if (currSupplyState == "BREAK_CONFIRMED" && lastSupplyBreakState != "BREAK_CONFIRMED") {
                val title = "🟢 SUPPLY ZONE BREAK CONFIRMED!"
                val msg = "Harga $priceStr tembus Supply • Siap Rally Lanjut • Aksi: ${status.context.action}"
                sendAlert(NOTIF_ID_ACTION, title, msg)
            }
            lastSupplyBreakState = currSupplyState

            val currDemandState = sdBreak.demandState
            if (currDemandState == "BREAK_CONFIRMED" && lastDemandBreakState != "BREAK_CONFIRMED") {
                val title = "🔴 DEMAND ZONE BREAK CONFIRMED!"
                val msg = "Harga $priceStr jebol Demand • Siap Drop Lanjut • Aksi: ${status.context.action}"
                sendAlert(NOTIF_ID_ACTION, title, msg)
            }
            lastDemandBreakState = currDemandState
        }

        // 7. Check High Confluence Radar (80%+ BUY / SELL with CF vs VR Mode)
        val conv = status.conviction
        val convDir = conv.dir.uppercase()
        val convScore = conv.score
        val convMax = if (conv.max > 0) conv.max else 5
        val convPct = if (convMax > 0) (convScore.toDouble() / convMax) * 100 else 0.0
        val isHighConfluence = convPct >= 75.0 && (convDir == "BUY" || convDir == "SELL")

        val nowMs = System.currentTimeMillis()
        if (isHighConfluence && prefs.isConfluenceAlertEnabled) {
            val d1Dir = status.regime.d1.uppercase()
            val isVR = (convDir == "SELL" && d1Dir == "BUY") || (convDir == "BUY" && d1Dir == "SELL")
            val modeStr = if (isVR) "VR RETEST (PULLBACK)" else "CF MODE (WITH TREND)"
            val actionStr = if (isVR) {
                if (convDir == "SELL") "🔴 SELL PULLBACK (VR) • TP di Demand D1" else "🟢 BUY PULLBACK (VR) • TP di Supply S1"
            } else {
                if (convDir == "BUY") "🟢 BUY BREAKOUT (CF) • Hold Trend" else "🔴 SELL BREAKOUT (CF) • Hold Trend"
            }

            if (lastConfluenceAlertDir != convDir || (nowMs - lastConfluenceAlertTime) > 300_000L) {
                lastConfluenceAlertDir = convDir
                lastConfluenceAlertTime = nowMs
                val emoji = if (convDir == "BUY") "🟢" else "🔴"
                val title = "$emoji KONFLUENSI TINGGI: ${convPct.toInt()}% $convDir [$modeStr]"
                val msg = "Harga $priceStr • $actionStr • Alignment: ${Formatters.formatPercent(status.regime.alignmentPct)} • Grade: ${conv.grade}"
                sendAlert(NOTIF_ID_CONFLUENCE, title, msg)
            }
        } else if (!isHighConfluence) {
            if (convDir == "WAIT" || convPct < 50.0) {
                lastConfluenceAlertDir = null
            }
        }

        // 8. Check S&D Key Zone Touch Alerts (Supply S1 / Demand D1)
        val roadmap = status.sdZones?.roadmap
        if (roadmap != null && prefs.isZoneTouchEnabled) {
            val currentPrice = status.price
            val s1 = roadmap.supply.firstOrNull()
            val d1 = roadmap.demand.firstOrNull()

            // Check Supply S1 touch
            if (s1 != null && currentPrice >= s1.lo - 1.5 && currentPrice <= s1.hi + 1.5) {
                val zoneKey = "S1_${s1.lo.toInt()}"
                if (lastTouchedZone != zoneKey || (nowMs - lastTouchedZoneTime) > 180_000L) {
                    lastTouchedZone = zoneKey
                    lastTouchedZoneTime = nowMs
                    val tfTag = if (s1.score >= 90) "[D1]" else if (s1.score >= 80) "[H4]" else if (s1.score >= 65) "[H1]" else "[M30]"
                    val title = "🔴 HARGA MENYENTUH SUPPLY S1 $tfTag (${Formatters.formatPrice(s1.lo)})"
                    val msg = "Harga $priceStr berada di Zona Supply • Kekuatan: ${s1.strength} • Uji ${s1.retestCount}x • Siap Pantulan / Pullback SELL!"
                    sendAlert(NOTIF_ID_ZONE_TOUCH, title, msg)
                }
            }
            // Check Demand D1 touch
            else if (d1 != null && currentPrice >= d1.lo - 1.5 && currentPrice <= d1.hi + 1.5) {
                val zoneKey = "D1_${d1.hi.toInt()}"
                if (lastTouchedZone != zoneKey || (nowMs - lastTouchedZoneTime) > 180_000L) {
                    lastTouchedZone = zoneKey
                    lastTouchedZoneTime = nowMs
                    val tfTag = if (d1.score >= 90) "[D1]" else if (d1.score >= 80) "[H4]" else if (d1.score >= 65) "[H1]" else "[M30]"
                    val title = "🟢 HARGA MENYENTUH DEMAND D1 $tfTag (${Formatters.formatPrice(d1.hi)})"
                    val msg = "Harga $priceStr berada di Zona Demand • Kekuatan: ${d1.strength} • Uji ${d1.retestCount}x • Siap Pantulan / Bounce BUY!"
                    sendAlert(NOTIF_ID_ZONE_TOUCH, title, msg)
                }
            } else {
                if (s1 != null && d1 != null && (currentPrice < s1.lo - 3.0 && currentPrice > d1.hi + 3.0)) {
                    lastTouchedZone = null
                }
            }
        }

        // 9. Check Bookmap Mega Wall Alert (>= 100 Lots)
        val liq = status.liquidity
        if (liq.askWallSize >= 100.0) {
            val wallKey = "ASK_${liq.askWallPrice.toInt()}_${liq.askWallSize.toInt()}"
            if (lastMegaWallNotified != wallKey) {
                lastMegaWallNotified = wallKey
                val title = "🐋 BOOKMAP MEGA ASK WALL DETECTED (${liq.askWallSize.toInt()}L)"
                val msg = "Tembok Ask Besar di $${Formatters.formatPrice(liq.askWallPrice)} (${liq.askWallSize.toInt()} Lot) • Penghalang Kuat ke Atas!"
                sendAlert(NOTIF_ID_MEGA_WALL, title, msg)
            }
        } else if (liq.bidWallSize >= 100.0) {
            val wallKey = "BID_${liq.bidWallPrice.toInt()}_${liq.bidWallSize.toInt()}"
            if (lastMegaWallNotified != wallKey) {
                lastMegaWallNotified = wallKey
                val title = "🐋 BOOKMAP MEGA BID WALL DETECTED (${liq.bidWallSize.toInt()}L)"
                val msg = "Tembok Bid Besar di $${Formatters.formatPrice(liq.bidWallPrice)} (${liq.bidWallSize.toInt()} Lot) • Penahan Kuat ke Bawah!"
                sendAlert(NOTIF_ID_MEGA_WALL, title, msg)
            }
        }
    }

    fun sendTestNotification() {
        sendAlert(
            9999,
            "⚡ TES NOTIFIKASI SIGNAL",
            "Sistem Push Alert Chain Reaction Aktif & Terhubung ke Server MT5!"
        )
    }

    private fun sendAlert(notificationId: Int, title: String, message: String) {
        val launchIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            notificationId,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, CHANNEL_ALERTS)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)

        if (prefs.isSoundVibrateEnabled) {
            builder.setDefaults(NotificationCompat.DEFAULT_ALL)
        } else {
            builder.setVibrate(null).setSound(null)
        }

        notificationManager.notify(notificationId, builder.build())
    }

    companion object {
        const val CHANNEL_ALERTS = "trading_alerts_channel"
        const val NOTIF_ID_D1_FLIP = 1001
        const val NOTIF_ID_H4_FLIP = 1002
        const val NOTIF_ID_H1_FLIP = 1003
        const val NOTIF_ID_M30_FLIP = 1004
        const val NOTIF_ID_M15_FLIP = 1005
        const val NOTIF_ID_M5_FLIP = 1006
        const val NOTIF_ID_M5_CF = 1007
        const val NOTIF_ID_ACTION = 1008
        const val NOTIF_ID_CHAIN = 1009
        const val NOTIF_ID_SWEEP = 1010
        const val NOTIF_ID_NEWS = 1011
        const val NOTIF_ID_CONFLUENCE = 1012
        const val NOTIF_ID_ZONE_TOUCH = 1013
        const val NOTIF_ID_MEGA_WALL = 1014

        @Volatile
        private var instance: NotificationHelper? = null

        fun getInstance(context: Context): NotificationHelper {
            return instance ?: synchronized(this) {
                instance ?: NotificationHelper(context.applicationContext).also { instance = it }
            }
        }
    }
}