package com.dadang.chainreaction.ui.screens.command

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.ElectricBolt
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.data.model.CalendarEvent
import com.dadang.chainreaction.data.model.MomentumSignal
import com.dadang.chainreaction.data.model.SignalsInfo
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.ui.components.CountdownBar
import com.dadang.chainreaction.ui.components.CyberCard
import com.dadang.chainreaction.ui.components.DeltaHistoryChart
import com.dadang.chainreaction.ui.components.DirectionPill
import com.dadang.chainreaction.ui.components.LivePriceHeader
import com.dadang.chainreaction.ui.components.MarketOverviewCard
import com.dadang.chainreaction.ui.components.MetricBox
import com.dadang.chainreaction.ui.components.SectionHeader
import com.dadang.chainreaction.ui.components.SpeedometerGauge
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BgCyberDark
import com.dadang.chainreaction.ui.theme.BorderAccent
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonAmberBg
import com.dadang.chainreaction.ui.theme.NeonAmberBorder
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonCyanBg
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonGreenBg
import com.dadang.chainreaction.ui.theme.NeonGreenBorder
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.NeonRedBg
import com.dadang.chainreaction.ui.theme.NeonRedBorder
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.Formatters

// Konstanta ambang batas jarak ke liquidity wall untuk memicu warning (dalam USD skala XAUUSD)
const val WALL_PROXIMITY_THRESHOLD_USD = 3.0
// Konstanta ambang batas waktu rilis berita high-impact (dalam menit)
const val HIGH_IMPACT_NEWS_THRESHOLD_MINS = 30L

@Composable
fun CommandScreen(
    status: SultanStatus?,
    calendarEvents: List<CalendarEvent> = emptyList(),
    priceDeltaDirection: Int = 0,
    modifier: Modifier = Modifier
) {
    if (status == null) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(BgCyberDark),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator(color = NeonCyan, modifier = Modifier.size(36.dp))
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = "Menghubungkan ke Chain Reaction Engine...",
                    fontSize = 12.sp,
                    color = TextSecondary
                )
            }
        }
        return
    }

    val scrollState = rememberScrollState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BgCyberDark)
            .verticalScroll(scrollState)
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        // =========================================================================
        // ⚡ FLASH ALERT ENTRY: LIVE PULSING ENTRY BANNER (BREAKOUT / BOUNCE / COMPRESSION)
        // =========================================================================
        LiveEntryPulsingBanner(status = status)

        // =========================================================================
        // 🥇 PRIORITAS 1: HARGA + BIAS ARAH (PRICE & MULTI-TIMEFRAME REGIME BIAS)
        // =========================================================================
        PriceAndBiasHeroCard(
            status = status,
            priceDeltaDirection = priceDeltaDirection
        )

        // =========================================================================
        // 🥈 PRIORITAS 2: CHAIN SIGNAL (signals.chain_signal - Layer & Arah)
        // =========================================================================
        ChainSignalHeroBanner(status = status)

        // =========================================================================
        // 🥉 PRIORITAS 3: CONVICTION GRADE (conviction.grade + conviction.score/max)
        // =========================================================================
        ConvictionGradeCard(status = status)

        // =========================================================================
        // ⚠️ PRIORITAS 4: SLOT WARNING KHUSUS (Hanya muncul jika ada kondisi darurat)
        // =========================================================================
        WarningSlotSection(
            status = status,
            calendarEvents = calendarEvents
        )

        // =========================================================================
        // 🏎️ SECTION PENDUKUNG: RADIAL SPEEDOMETER BREAKOUT VELOCITY GAUGE
        // =========================================================================
        val m5Text = status.signals.momentumM5?.text ?: ""
        val velocityMultiplier = parseMultiplier(m5Text).coerceAtLeast((status.flow.pulsePct / 20f).toFloat())

        SpeedometerGauge(
            value = velocityMultiplier,
            maxValue = 5.0f,
            unit = "x",
            label = "BREAKOUT VELOCITY SPEEDOMETER",
            direction = status.signals.momentumM5?.dir ?: "NEUTRAL",
            statusText = if (m5Text.isNotBlank()) m5Text else "NORMAL PULSE"
        )

        // =========================================================================
        // ⚡ SECTION PENDUKUNG: BREAKOUT MOMENTUM TRIAD (M5 Core, Bookmap, Footprint)
        // =========================================================================
        LiveBreakoutMomentumCard(
            signals = status.signals,
            m5Countdown = status.signals.countdown.m5
        )

        // =========================================================================
        // 📊 SECTION PENDUKUNG: ORDER FLOW & CVD PULSE + DELTA HISTORY CANVAS CHART
        // =========================================================================
        OrderFlowPulseCard(status = status)

        // =========================================================================
        // ⏱️ SECTION PENDUKUNG: MULTI-TIMEFRAME CANDLE COUNTDOWNS
        // =========================================================================
        CountdownBar(countdown = status.signals.countdown)

        // =========================================================================
        // 🧱 SECTION PENDUKUNG: NEAREST WALL LIQUIDITY DETAIL
        // =========================================================================
        NearestWallCard(status = status)

        // =========================================================================
        // 🌐 SECTION PENDUKUNG: MARKET OVERVIEW & VALUE AREA (Option A - Expandable)
        // =========================================================================
        MarketOverviewCard(location = status.location, usd = status.usd)

        Spacer(modifier = Modifier.height(80.dp)) // padding for bottom nav
    }
}

/**
 * 🥇 PRIORITAS 1: HARGA + BIAS ARAH
 * Price, Balance/Equity, serta Ringkasan Regime H4, M30, M5 (Searah / Tidak).
 */
@Composable
private fun PriceAndBiasHeroCard(
    status: SultanStatus,
    priceDeltaDirection: Int
) {
    val regime = status.regime
    val isAligned = regime.alignmentPct >= 75.0
    val isBuyBias = regime.htfBias.contains("BUY") || regime.htfBias.contains("BULLISH")
    val isSellBias = regime.htfBias.contains("SELL") || regime.htfBias.contains("BEARISH")

    val biasColor = when {
        isBuyBias -> NeonGreen
        isSellBias -> NeonRed
        else -> NeonAmber
    }

    CyberCard(
        backgroundColor = BgCardElevated,
        borderColor = biasColor.copy(alpha = 0.5f),
        borderWidth = 1.2f
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Live Price & Balance Header
            LivePriceHeader(
                symbol = status.symbol,
                price = status.price,
                balance = status.balance,
                equity = status.equity,
                priceDeltaDirection = priceDeltaDirection
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Multi-Timeframe Bias Alignment Strip
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(Color(0xFF0C1420))
                    .border(BorderStroke(0.8.dp, BorderSubtle), RoundedCornerShape(8.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        TimeframeBiasPill(tf = "H4", bias = regime.h4)
                        TimeframeBiasPill(tf = "M30", bias = regime.m30)
                        TimeframeBiasPill(tf = "M5", bias = "${regime.m5} (${regime.m5Status})")
                    }

                    // Alignment Badge
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(if (isAligned) (if (isBuyBias) NeonGreenBg else NeonRedBg) else NeonAmberBg)
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = if (isAligned) "${Formatters.formatPercent(regime.alignmentPct)} SEARAH" else "${Formatters.formatPercent(regime.alignmentPct)} MIXED",
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Black,
                            fontFamily = FontFamily.Monospace,
                            color = if (isAligned) (if (isBuyBias) NeonGreen else NeonRed) else NeonAmber
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TimeframeBiasPill(tf: String, bias: String) {
    val isBuy = bias.contains("BUY")
    val isSell = bias.contains("SELL")
    val col = if (isBuy) NeonGreen else if (isSell) NeonRed else TextMuted

    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = "$tf:",
            fontSize = 9.5.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            color = TextSecondary
        )
        Spacer(modifier = Modifier.width(3.dp))
        Text(
            text = bias,
            fontSize = 9.5.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black,
            color = col
        )
    }
}

/**
 * 🥈 PRIORITAS 2: CHAIN SIGNAL (signals.chain_signal)
 * Ada sinyal aktif (Layer + Arah) atau lagi nunggu.
 */
@Composable
private fun ChainSignalHeroBanner(status: SultanStatus) {
    val chain = status.signals.chainSignal
    val isLayerActive = (chain?.layer ?: 0) > 0
    val isBuy = chain?.dir?.contains("BUY") == true
    val isSell = chain?.dir?.contains("SELL") == true

    val (accentColor, bgColor) = when {
        isBuy -> Pair(NeonGreen, NeonGreen.copy(alpha = 0.14f))
        isSell -> Pair(NeonRed, NeonRed.copy(alpha = 0.14f))
        else -> Pair(NeonAmber, NeonAmber.copy(alpha = 0.12f))
    }

    // Breathing glow animation on border
    val infiniteTransition = rememberInfiniteTransition(label = "chain_glow")
    val borderAlpha by infiniteTransition.animateFloat(
        initialValue = 0.5f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1100),
            repeatMode = RepeatMode.Reverse
        ),
        label = "chain_border_glow"
    )

    CyberCard(
        backgroundColor = bgColor,
        borderColor = accentColor.copy(alpha = if (isLayerActive) borderAlpha else 0.4f),
        borderWidth = if (isLayerActive) 1.8f else 1.0f
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Hub,
                        contentDescription = null,
                        tint = accentColor,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "CHAIN REACTION SIGNAL",
                        fontSize = 11.5.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = accentColor,
                        letterSpacing = 1.sp
                    )
                }

                // Layer Badge
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(if (isBuy) NeonGreenBg else if (isSell) NeonRedBg else NeonCyanBg)
                        .border(
                            BorderStroke(
                                1.dp,
                                if (isBuy) NeonGreenBorder else if (isSell) NeonRedBorder else BorderAccent
                            ),
                            RoundedCornerShape(6.dp)
                        )
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = if (isLayerActive) "LAYER ${chain?.layer} (${chain?.dir})" else "STANDBY (LAYER 0)",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = accentColor
                    )
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            // Action Verdict (e.g. BUY PULLBACK / SELL BREAKOUT)
            Text(
                text = status.context.action.replace("_", " "),
                fontSize = 22.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                color = accentColor,
                letterSpacing = 0.5.sp
            )

            Spacer(modifier = Modifier.height(6.dp))

            // Context Mini Tags
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                ContextMiniTag(label = "FLOW", value = status.context.flow, modifier = Modifier.weight(1f))
                ContextMiniTag(label = "LIQUIDITY", value = status.context.liquidity, modifier = Modifier.weight(1f))
                ContextMiniTag(label = "REGIME", value = status.context.regime, modifier = Modifier.weight(1f))
            }
        }
    }
}

/**
 * 🥉 PRIORITAS 3: CONVICTION GRADE (conviction.grade + conviction.score/max)
 * Seberapa yakin sistem terhadap setup saat ini.
 */
@Composable
private fun ConvictionGradeCard(status: SultanStatus) {
    val conviction = status.conviction
    val score = conviction.score
    val maxScore = conviction.max
    val isHighConviction = score >= 4

    val gradeColor = when {
        conviction.grade.startsWith("A") -> GoldAccent
        conviction.grade.startsWith("B") -> NeonCyan
        conviction.grade.startsWith("C") -> NeonAmber
        else -> NeonRed
    }

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Shield,
                        contentDescription = null,
                        tint = gradeColor,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "CONVICTION SETUP MATRIX",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = gradeColor,
                        letterSpacing = 0.8.sp
                    )
                }

                DirectionPill(
                    direction = "GRADE ${conviction.grade}",
                    fontSize = 11.sp
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "Conviction Score",
                    value = "$score / $maxScore",
                    subValue = if (isHighConviction) "HIGH CONFIDENCE" else "MODERATE",
                    valueColor = if (isHighConviction) NeonGreen else NeonAmber,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Mode",
                    value = conviction.mode,
                    subValue = "Dir: ${conviction.dir}",
                    valueColor = if (conviction.dir == "BUY") NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            // Chain Done vs Next Summary
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(6.dp))
                    .background(BgCardElevated)
                    .border(BorderStroke(0.6.dp, BorderSubtle), RoundedCornerShape(6.dp))
                    .padding(horizontal = 8.dp, vertical = 6.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "DONE: ${conviction.chainDone}",
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = NeonCyan
                    )
                    Text(
                        text = "NEXT: ${conviction.chainNext}",
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = NeonAmber
                    )
                }
            }
        }
    }
}

/**
 * ⚠️ PRIORITAS 4: SLOT WARNING KHUSUS (BARU)
 * Area yang HANYA MUNCUL jika ada kondisi darurat:
 * 1. Jarak ke Liquidity Wall <= 3.0 USD
 * 2. Berita High-Impact (Forex Factory) dalam <= 30 menit
 * Jika tidak ada warning aktif, slot ini otomatis disembunyikan/kosong!
 */
@Composable
private fun WarningSlotSection(
    status: SultanStatus,
    calendarEvents: List<CalendarEvent>
) {
    val warnings = mutableListOf<WarningItemData>()

    // 1. Check Wall Proximity Warning (jarak <= WALL_PROXIMITY_THRESHOLD_USD)
    val liq = status.liquidity
    if (liq.nearestWallDistance in 0.01..WALL_PROXIMITY_THRESHOLD_USD) {
        warnings.add(
            WarningItemData(
                title = "HARGA DEKAT LIQUIDITY WALL ${liq.nearestWallSide}",
                description = "Jarak hanya $${Formatters.formatPrice(liq.nearestWallDistance)} (${if (liq.nearestWallSide == "BID") Formatters.formatLot(liq.bidWallSize) else Formatters.formatLot(liq.askWallSize)}L) • Potensi pantulan/penembusan",
                severityColor = NeonAmber
            )
        )
    }

    // 2. Check High-Impact News Imminent (mins_until <= 30 menit & impact == "high")
    val imminentHighNews = calendarEvents.filter { event ->
        event.minsUntil in 0..HIGH_IMPACT_NEWS_THRESHOLD_MINS &&
                event.impact.equals("high", ignoreCase = true)
    }
    imminentHighNews.forEach { event ->
        warnings.add(
            WarningItemData(
                title = "HIGH-IMPACT NEWS SEBENTAR LAGI (${event.minsUntil}m)",
                description = "${event.name} [${event.country}] • Jam: ${event.time} • Waspadai lonjakan volatilitas!",
                severityColor = NeonRed
            )
        )
    }

    // 3. Check S&D Zone Compression Warning (<1 USD)
    val sdDecision = status.sdZones?.decision
    if (sdDecision?.compression == true) {
        warnings.add(
            WarningItemData(
                title = "S&D ZONE COMPRESSION (< 1 USD)",
                description = if (sdDecision.reasonText.isNotBlank()) sdDecision.reasonText else "Supply & Demand sangat sempit (<1 USD) • Tunggu konfirmasi breakout!",
                severityColor = NeonAmber
            )
        )
    }

    // Tampilkan hanya jika ada warning aktif
    AnimatedVisibility(
        visible = warnings.isNotEmpty(),
        enter = fadeIn() + expandVertically(),
        exit = fadeOut() + shrinkVertically()
    ) {
        CyberCard(
            backgroundColor = NeonAmber.copy(alpha = 0.1f),
            borderColor = NeonAmber.copy(alpha = 0.7f),
            borderWidth = 1.4f
        ) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Warning,
                            contentDescription = null,
                            tint = NeonAmber,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "COMMANDER WARNING ALERT",
                            fontSize = 11.5.sp,
                            fontWeight = FontWeight.Black,
                            fontFamily = FontFamily.Monospace,
                            color = NeonAmber,
                            letterSpacing = 1.sp
                        )
                    }

                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(NeonAmber)
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = "${warnings.size} ATTENTION",
                            fontSize = 9.5.sp,
                            fontWeight = FontWeight.Black,
                            fontFamily = FontFamily.Monospace,
                            color = BgCyberDark
                        )
                    }
                }

                // Stack vertikal semua warning yang sedang aktif
                warnings.forEach { item ->
                    WarningItemRow(item = item)
                }
            }
        }
    }
}

private data class WarningItemData(
    val title: String,
    val description: String,
    val severityColor: Color
)

@Composable
private fun WarningItemRow(item: WarningItemData) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(item.severityColor.copy(alpha = 0.12f))
            .border(BorderStroke(0.8.dp, item.severityColor.copy(alpha = 0.5f)), RoundedCornerShape(6.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp)
    ) {
        Column {
            Text(
                text = "⚠️ " + item.title,
                fontSize = 11.5.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                color = item.severityColor
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = item.description,
                fontSize = 10.5.sp,
                color = TextPrimary,
                lineHeight = 14.sp
            )
        }
    }
}

private fun parseMultiplier(text: String): Float {
    if (text.isBlank()) return 1.0f
    val regex = Regex("([0-9]+(?:\\.[0-9]+)?)x")
    val match = regex.find(text)
    return match?.groupValues?.get(1)?.toFloatOrNull() ?: 1.0f
}

@Composable
private fun LiveBreakoutMomentumCard(
    signals: SignalsInfo,
    m5Countdown: Long
) {
    val m5Core = signals.momentumM5
    val m5Bm = signals.momentumM5Bookmap
    val m5Fp = signals.momentumM5Footprint

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Bolt,
                        contentDescription = null,
                        tint = GoldAccent,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "BREAKOUT MOMENTUM TRIAD",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = GoldAccent
                    )
                }

                Text(
                    text = "M5 CLOSE: ${Formatters.formatCountdownSeconds(m5Countdown)}",
                    fontSize = 9.5.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    color = if (m5Countdown <= 30) NeonAmber else NeonCyan
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 3 Momentum Tiles
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MomentumHeroTile(
                    title = "M5 CORE EA",
                    signal = m5Core,
                    subLabel = "Velocity",
                    modifier = Modifier.weight(1f)
                )
                MomentumHeroTile(
                    title = "BOOKMAP",
                    signal = m5Bm,
                    subLabel = "Book Pressure",
                    modifier = Modifier.weight(1f)
                )
                MomentumHeroTile(
                    title = "FOOTPRINT",
                    signal = m5Fp,
                    subLabel = "Tape Delta",
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun MomentumHeroTile(
    title: String,
    signal: MomentumSignal?,
    subLabel: String,
    modifier: Modifier = Modifier
) {
    val dir = signal?.dir?.trim()?.uppercase() ?: ""
    val isBuy = dir == "BUY" || dir.contains("BUY")
    val isSell = dir == "SELL" || dir.contains("SELL")
    val isStrong = signal?.text?.contains("STRONG", ignoreCase = true) == true

    val (tileBorder, tileBg, textDirColor) = when {
        isBuy -> Triple(if (isStrong) NeonGreen else NeonGreenBorder, NeonGreenBg, NeonGreen)
        isSell -> Triple(if (isStrong) NeonRed else NeonRedBorder, NeonRedBg, NeonRed)
        else -> Triple(BorderSubtle, BgCyberDark, TextMuted)
    }

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(tileBg)
            .border(BorderStroke(if (isStrong) 1.2.dp else 0.8.dp, tileBorder), RoundedCornerShape(8.dp))
            .padding(horizontal = 6.dp, vertical = 8.dp)
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = title,
                fontSize = 8.5.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                color = TextSecondary,
                letterSpacing = 0.5.sp
            )

            Spacer(modifier = Modifier.height(3.dp))

            Text(
                text = signal?.text?.ifBlank { "-" } ?: "-",
                fontSize = 11.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                color = textDirColor,
                maxLines = 1
            )

            Spacer(modifier = Modifier.height(2.dp))

            Text(
                text = subLabel,
                fontSize = 8.sp,
                fontFamily = FontFamily.Monospace,
                color = TextMuted,
                maxLines = 1
            )
        }
    }
}

@Composable
private fun OrderFlowPulseCard(status: SultanStatus) {
    val flow = status.flow

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "ORDER FLOW & CVD PULSE",
                icon = Icons.Default.Speed,
                badgeText = "DOM: ${flow.flowDominant}",
                badgeColor = if (flow.flowDominant == "BUY") NeonGreen else NeonRed
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "CVD",
                    value = "${flow.cvd}",
                    valueColor = if (flow.cvd >= 0) NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "1M Delta",
                    value = "${flow.delta1m}",
                    valueColor = if (flow.delta1m >= 0) NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Buy Vol %",
                    value = Formatters.formatPercent(flow.volRatioBuyPct),
                    valueColor = if (flow.volRatioBuyPct >= 50) NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Pulse %",
                    value = Formatters.formatPercent(flow.pulsePct),
                    valueColor = NeonCyan,
                    modifier = Modifier.weight(1f)
                )
            }

            // 📊 DELTA HISTORY CANVAS BAR CHART
            if (flow.deltaHistory.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                DeltaHistoryChart(
                    deltaHistory = flow.deltaHistory,
                    currentDelta = flow.delta1m
                )
            }
        }
    }
}

@Composable
private fun ContextMiniTag(label: String, value: String, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(4.dp))
            .background(BgCardElevated)
            .border(BorderStroke(0.6.dp, BorderSubtle), RoundedCornerShape(4.dp))
            .padding(horizontal = 4.dp, vertical = 3.dp)
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = label,
                fontSize = 8.sp,
                fontFamily = FontFamily.Monospace,
                color = TextMuted
            )
            Text(
                text = value,
                fontSize = 9.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = TextPrimary,
                maxLines = 1
            )
        }
    }
}

@Composable
private fun NearestWallCard(status: SultanStatus) {
    val liq = status.liquidity
    val isBid = liq.nearestWallSide == "BID"

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "NEAREST LIQUIDITY WALL",
                badgeText = "${liq.nearestWallSide} WALL (${Formatters.formatPrice(liq.nearestWallDistance)} pts)",
                badgeColor = if (isBid) NeonGreen else NeonRed
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "Bid Wall",
                    value = "${Formatters.formatPrice(liq.bidWallPrice)} (${Formatters.formatLot(liq.bidWallSize)}L)",
                    subValue = "Ratio: ${liq.bidWallRatio}x | ${liq.bidWallCount} walls (${liq.bidWallTotalLot}L)",
                    valueColor = NeonGreen,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Ask Wall",
                    value = "${Formatters.formatPrice(liq.askWallPrice)} (${Formatters.formatLot(liq.askWallSize)}L)",
                    subValue = "Ratio: ${liq.askWallRatio}x | ${liq.askWallCount} walls (${liq.askWallTotalLot}L)",
                    valueColor = NeonRed,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun LiveEntryPulsingBanner(status: SultanStatus) {
    val sdBreak = status.sdZones?.breakStatus
    val supplyState = sdBreak?.supplyState ?: ""
    val demandState = sdBreak?.demandState ?: ""
    val decision = status.sdZones?.decision
    val d1 = status.sdZones?.roadmap?.demand?.firstOrNull()
    val s1 = status.sdZones?.roadmap?.supply?.firstOrNull()
    val isBuyConfirmed = supplyState == "BREAK_CONFIRMED"
    val isSellConfirmed = demandState == "BREAK_CONFIRMED"
    val isAttempting = supplyState.contains("MOMENTUM") || demandState.contains("MOMENTUM") || supplyState.contains("CLOSE") || demandState.contains("CLOSE")
    val isCompression = decision?.compression == true
    val isRejection = supplyState.contains("REJECTION") || demandState.contains("REJECTION")
    val isMegaDemand = (d1?.totalLot ?: 0.0) >= 700.0 && decision?.location == "INSIDE_DEMAND"
    val isMegaSupply = (s1?.totalLot ?: 0.0) >= 700.0 && decision?.location == "INSIDE_SUPPLY"

    val isVisible = isBuyConfirmed || isSellConfirmed || isAttempting || isCompression || isRejection || isMegaDemand || isMegaSupply

    if (!isVisible) return

    val infiniteTransition = rememberInfiniteTransition(label = "pulse_entry")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.30f,
        targetValue = 0.98f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 650, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alpha"
    )

    val (glowColor, titleText, subText) = when {
        isBuyConfirmed -> Triple(
            NeonGreen,
            "🚀 [SETUP 2: VACUUM BREAKOUT] S1 RESMI JEBOL NAIK!",
            "Lilin M5 Body Close Sah di Atas S1 • Target TP ➔ Zona Supply S2"
        )
        isSellConfirmed -> Triple(
            NeonRed,
            "🚀 [SETUP 2: VACUUM BREAKDOWN] D1 RESMI JEBOL TURUN!",
            "Lilin M5 Body Close Sah di Bawah D1 • Target TP ➔ Zona Demand D2"
        )
        isMegaDemand -> Triple(
            NeonGreen,
            "💎 [SETUP 1: MEGA FORTRESS REBOUND] BENTENG DEMAND ${d1?.totalLot?.toInt()}L!",
            "Area Akumulasi Institusi $${d1?.lo ?: 0.0}-$${d1?.hi ?: 0.0} • Cari Konfirmasi BUY Pantulan (TP ➔ S1/POC)"
        )
        isMegaSupply -> Triple(
            NeonRed,
            "💎 [SETUP 1: MEGA FORTRESS REBOUND] BENTENG SUPPLY ${s1?.totalLot?.toInt()}L!",
            "Area Distribusi Institusi $${s1?.lo ?: 0.0}-$${s1?.hi ?: 0.0} • Cari Konfirmasi SELL Pantulan (TP ➔ D1/POC)"
        )
        isRejection -> Triple(
            NeonCyan,
            "🛡️ [SETUP 3: SWEEP REVERSAL] ZONA BERHASIL MENAHAN (REJECTION)",
            "Percobaan tembus gagal. Harga memantul balik ke sisi seberang range!"
        )
        isCompression -> Triple(
            NeonAmber,
            "🚨 ZONA SEMPIT (< 1 USD) — NO TRADE ZONE",
            "Supply & Demand jepit rapat. EA dilarang entry, tunggu breakout!"
        )
        supplyState.contains("MOMENTUM") || supplyState.contains("CLOSE") -> Triple(
            NeonAmber,
            "⏳ S1 UJI TEMBUS NAIK (RUNNING CANDLE)",
            "Sedang mendobrak Supply ke atas • Wajib TUNGGU Lilin M5 Tutup/Close!"
        )
        else -> Triple(
            NeonAmber,
            "⏳ D1 UJI TEMBUS TURUN (RUNNING CANDLE)",
            "Sedang mendobrak Demand ke bawah • Wajib TUNGGU Lilin M5 Tutup/Close!"
        )
    }

    CyberCard(
        backgroundColor = glowColor.copy(alpha = 0.12f),
        borderColor = glowColor.copy(alpha = alpha),
        borderWidth = 2.0f
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(glowColor.copy(alpha = alpha))
            )
            Spacer(modifier = Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = titleText,
                    fontSize = 12.0.sp,
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Black,
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                    color = glowColor,
                    letterSpacing = 0.5.sp
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = subText,
                    fontSize = 10.0.sp,
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                    color = TextPrimary
                )
            }
        }
    }
}
