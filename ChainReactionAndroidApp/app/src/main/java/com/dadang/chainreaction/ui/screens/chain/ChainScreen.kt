package com.dadang.chainreaction.ui.screens.chain

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AltRoute
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.data.model.RegimeInfo
import com.dadang.chainreaction.data.model.SignalsInfo
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.data.model.SdZonesInfo
import com.dadang.chainreaction.data.model.SdBreak
import com.dadang.chainreaction.data.model.SdZone
import com.dadang.chainreaction.data.model.SdDecision
import com.dadang.chainreaction.data.model.SdRoadmap
import com.dadang.chainreaction.ui.components.CyberCard
import com.dadang.chainreaction.ui.components.DirectionPill
import com.dadang.chainreaction.ui.components.MetricBox
import com.dadang.chainreaction.ui.components.SectionHeader
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BgCyberDark
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.Formatters

@Composable
fun ChainScreen(
    status: SultanStatus?,
    modifier: Modifier = Modifier
) {
    if (status == null) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(BgCyberDark),
            contentAlignment = Alignment.Center
        ) {
            CircularProgressIndicator(color = NeonCyan, modifier = Modifier.size(36.dp))
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
        // 1. Timeframe Regime Matrix (D1 .. M1)
        TimeframeRegimeMatrixCard(regime = status.regime)
        
        // S&D Zones Engine
        SupplyDemandCard(status = status)

        // 2. Chain Signal Progression & Layers
        ChainProgressionCard(status = status)

        // 3. Momentum Triad (M5 EA, Bookmap, Footprint)
        MomentumTriadCard(signals = status.signals)

        // 4. Barriers, IVB & Volume Node Confluences
        TechnicalConfluencesCard(signals = status.signals)

        Spacer(modifier = Modifier.height(80.dp))
    }
}

@Composable
private fun TimeframeRegimeMatrixCard(regime: RegimeInfo) {
    val timeframes = listOf(
        Pair("D1", regime.d1),
        Pair("H4", regime.h4),
        Pair("H1", regime.h1),
        Pair("M30", regime.m30),
        Pair("M15", regime.m15),
        Pair("M5", regime.m5),
        Pair("M1", regime.m1)
    )

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "TIMEFRAME REGIME MATRIX",
                icon = Icons.Default.Hub,
                badgeText = "ALIGN: ${Formatters.formatPercent(regime.alignmentPct)}",
                badgeColor = if (regime.alignmentPct >= 70) NeonGreen else NeonAmber
            )

            // Matrix Pills Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                timeframes.forEach { (tf, dir) ->
                    TimeframeCell(
                        timeframe = tf,
                        direction = dir,
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "HTF Bias",
                    value = regime.htfBias,
                    valueColor = if (regime.htfBias == "BEARISH") NeonRed else NeonGreen,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Regime State",
                    value = regime.regime,
                    valueColor = NeonCyan,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "M5 Status",
                    value = regime.m5Status.replace("_", " "),
                    valueColor = if (regime.m5Status == "WITH_TREND") NeonGreen else NeonAmber,
                    modifier = Modifier.weight(1.2f)
                )
            }
        }
    }
}

@Composable
private fun TimeframeCell(
    timeframe: String,
    direction: String,
    modifier: Modifier = Modifier
) {
    val isBuy = direction.contains("BUY")
    val isSell = direction.contains("SELL")
    val (bgColor, textColor) = when {
        isBuy -> Pair(NeonGreen.copy(alpha = 0.15f), NeonGreen)
        isSell -> Pair(NeonRed.copy(alpha = 0.15f), NeonRed)
        else -> Pair(BgCardElevated, TextMuted)
    }

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(bgColor)
            .border(
                BorderStroke(
                    0.8.dp,
                    if (isBuy) NeonGreen.copy(alpha = 0.5f) else if (isSell) NeonRed.copy(alpha = 0.5f) else BorderSubtle
                ),
                RoundedCornerShape(6.dp)
            )
            .padding(vertical = 6.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = timeframe,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                color = TextSecondary
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = direction,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                color = textColor
            )
        }
    }
}

@Composable
private fun ChainProgressionCard(status: SultanStatus) {
    val conviction = status.conviction
    val chainSignal = status.signals.chainSignal

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "CHAIN REACTION PROGRESSION",
                icon = Icons.Default.AltRoute,
                badgeText = "LAYER ${chainSignal?.layer ?: 0} (${chainSignal?.dir ?: "-"})",
                badgeColor = if (chainSignal?.dir == "BUY") NeonGreen else NeonRed
            )

            // Flow Progression Track
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(BgCardElevated)
                    .border(BorderStroke(0.8.dp, BorderSubtle), RoundedCornerShape(8.dp))
                    .padding(10.dp)
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "COMPLETED CHAIN:",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            color = TextMuted
                        )
                        Text(
                            text = conviction.chainDone,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Black,
                            fontFamily = FontFamily.Monospace,
                            color = NeonGreen
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "TARGET NEXT:",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            color = TextMuted
                        )
                        Text(
                            text = conviction.chainNext,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Black,
                            fontFamily = FontFamily.Monospace,
                            color = NeonAmber
                        )
                    }
                    if (conviction.chainPending.isNotBlank() && conviction.chainPending != "-") {
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "PENDING TF:",
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                color = TextMuted
                            )
                            Text(
                                text = conviction.chainPending,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                color = TextSecondary
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MomentumTriadCard(signals: SignalsInfo) {
    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "MOMENTUM TRIAD SIGNALS",
                icon = Icons.Default.Bolt
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "M5 Core EA",
                    value = signals.momentumM5?.text ?: "-",
                    valueColor = if (signals.momentumM5?.dir == "BUY") NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "M5 Bookmap",
                    value = signals.momentumM5Bookmap?.text ?: "-",
                    valueColor = if (signals.momentumM5Bookmap?.dir == "BUY") NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "M5 Footprint",
                    value = signals.momentumM5Footprint?.text ?: "-",
                    valueColor = if (signals.momentumM5Footprint?.dir == "BUY") NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun TechnicalConfluencesCard(signals: SignalsInfo) {
    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "BARRIERS, IVB & NODES",
                icon = Icons.Default.Radar
            )

            // Barrier Warning
            if (!signals.barrierWarning.isNullOrBlank()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(6.dp))
                        .background(NeonAmber.copy(alpha = 0.12f))
                        .border(BorderStroke(0.8.dp, NeonAmber.copy(alpha = 0.4f)), RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 6.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Warning,
                            contentDescription = null,
                            tint = NeonAmber,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "BARRIER: ${signals.barrierWarning}",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            color = NeonAmber
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "IVB Range",
                    value = signals.ivb?.text ?: "-",
                    subValue = if (signals.ivb?.locked == true) "LOCKED" else "OPEN",
                    valueColor = GoldAccent,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Volume Node",
                    value = signals.volumeNode?.text ?: "-",
                    valueColor = NeonCyan,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "CVD Divergence",
                    value = signals.cvdDivergence?.status ?: "-",
                    valueColor = if (signals.cvdDivergence?.status?.contains("BEARISH") == true) NeonRed else TextSecondary,
                    modifier = Modifier.weight(1.2f)
                )
            }
        }
    }
}

@Composable
private fun SupplyDemandCard(status: SultanStatus) {
    val sdZones = status.sdZones ?: return
    val decision = sdZones.decision
    val roadmap = sdZones.roadmap
    val breakStatus = sdZones.breakStatus
    if (!sdZones.available && roadmap.supply.isEmpty() && roadmap.demand.isEmpty() && decision.focus.isBlank()) return
    
    val currentPrice = status.price
    val s1 = roadmap.supply.firstOrNull()
    val s2 = roadmap.supply.getOrNull(1)
    val d1 = roadmap.demand.firstOrNull()
    val d2 = roadmap.demand.getOrNull(1)
    
    val distToS1 = if (s1 != null && currentPrice > 0) (s1.lo - currentPrice).coerceAtLeast(0.0) else null
    val distToD1 = if (d1 != null && currentPrice > 0) (currentPrice - d1.hi).coerceAtLeast(0.0) else null

    CyberCard {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // 1. HEADER & POWER BAR
            SectionHeader(
                title = "S&D DEPTH RADAR & ORDER-FLOW",
                icon = Icons.Default.Radar,
                badgeText = if (decision.compression) "COMPRESSION (<1$)" else decision.marketState.ifBlank { "ACTIVE RANGE" },
                badgeColor = if (decision.compression) NeonAmber else if (decision.buyerPct > decision.sellerPct) NeonGreen else NeonRed
            )

            // Buyer vs Seller Dominance Power Bar
            BuyerSellerPowerBar(buyerPct = decision.buyerPct, sellerPct = decision.sellerPct)

            // 2. FOKUS & TACTICAL ALERT HUD
            TacticalFocusAlert(decision = decision)

            // 3. VERTICAL DEPTH RADAR FUNNEL (S2 -> S1 -> LIVE PRICE -> D1 -> D2)
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(BgCardElevated.copy(alpha = 0.6f))
                    .border(BorderStroke(0.8.dp, BorderSubtle), RoundedCornerShape(8.dp))
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // Label Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "VERTICAL DEPTH MAP",
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = TextMuted
                    )
                    Text(
                        text = "REAL BOOKMAP LIQUIDITY",
                        fontSize = 8.5.sp,
                        fontFamily = FontFamily.Monospace,
                        color = TextSecondary
                    )
                }

                // S2 Zone (Far Supply)
                if (s2 != null) {
                    SdZoneRowCard(zone = s2, label = "S2", isSupply = true, isPrimary = false)
                }

                // S1 Zone (Near Supply)
                if (s1 != null) {
                    SdZoneRowCard(zone = s1, label = "S1", isSupply = true, isPrimary = true)
                }

                // Center Price Laser Beam
                LivePriceLaserBeam(
                    price = currentPrice,
                    distToS1 = distToS1,
                    distToD1 = distToD1,
                    isCompression = decision.compression
                )

                // D1 Zone (Near Demand)
                if (d1 != null) {
                    SdZoneRowCard(zone = d1, label = "D1", isSupply = false, isPrimary = true)
                }

                // D2 Zone (Far Demand)
                if (d2 != null) {
                    SdZoneRowCard(zone = d2, label = "D2", isSupply = false, isPrimary = false)
                }
            }

            // 4. MOMENTUM BREAK PIPELINE HUD
            MomentumBreakPipelineCard(breakStatus = breakStatus)

            // 5. ORDER-FLOW COMBAT FEED (TERMINAL LOG)
            OrderFlowCombatFeed(
                decision = decision,
                breakStatus = breakStatus,
                s1 = s1,
                d1 = d1
            )

            // 6. DISCLAIMER
            Text(
                text = "⚠️ Disclaimer: Bukan saran finansial. Area observasi & pantau order-flow, BUKAN sinyal entry otomatis. Keputusan dan risiko di tangan Anda.",
                fontSize = 8.sp,
                fontFamily = FontFamily.Monospace,
                color = TextMuted,
                lineHeight = 11.sp
            )
        }
    }
}

@Composable
private fun BuyerSellerPowerBar(buyerPct: Int, sellerPct: Int) {
    val bPct = buyerPct.coerceIn(0, 100)
    val sPct = sellerPct.coerceIn(0, 100)

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = "BUY POWER: $bPct%",
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = NeonGreen
            )
            Text(
                text = "SELL POWER: $sPct%",
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = NeonRed
            )
        }
        Spacer(modifier = Modifier.height(3.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(3.dp))
                .background(BgCardElevated)
        ) {
            Row(modifier = Modifier.fillMaxSize()) {
                Box(
                    modifier = Modifier
                        .weight(if (bPct <= 0) 0.01f else bPct.toFloat())
                        .fillMaxSize()
                        .background(NeonGreen)
                )
                Box(
                    modifier = Modifier
                        .weight(if (sPct <= 0) 0.01f else sPct.toFloat())
                        .fillMaxSize()
                        .background(NeonRed)
                )
            }
        }
    }
}

@Composable
private fun TacticalFocusAlert(decision: SdDecision) {
    if (decision.focus.isBlank() && decision.locationText.isBlank()) return

    val isAlert = decision.compression || decision.marketState.contains("COMPRESSION")
    val borderColor = if (isAlert) NeonAmber else NeonCyan.copy(alpha = 0.5f)
    val bgColor = if (isAlert) NeonAmber.copy(alpha = 0.12f) else BgCardElevated

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(bgColor)
            .border(BorderStroke(0.8.dp, borderColor), RoundedCornerShape(6.dp))
            .padding(horizontal = 10.dp, vertical = 7.dp)
    ) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = decision.focus.ifBlank { "FOKUS: MONITORING ZONA" }.uppercase(),
                    fontSize = 11.5.sp,
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.Monospace,
                    color = if (isAlert) NeonAmber else NeonCyan
                )
                if (isAlert) {
                    Text(
                        text = "WAIT",
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = BgCyberDark,
                        modifier = Modifier
                            .clip(RoundedCornerShape(3.dp))
                            .background(NeonAmber)
                            .padding(horizontal = 5.dp, vertical = 1.dp)
                    )
                }
            }
            if (decision.locationText.isNotBlank()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = "POSISI: ${decision.locationText} • ${decision.reasonText}",
                    fontSize = 9.5.sp,
                    fontFamily = FontFamily.Monospace,
                    color = TextSecondary,
                    lineHeight = 13.sp
                )
            }
        }
    }
}

@Composable
private fun SdZoneRowCard(
    zone: SdZone,
    label: String,
    isSupply: Boolean,
    isPrimary: Boolean
) {
    val baseColor = if (isSupply) NeonRed else NeonGreen
    val alphaBorder = if (isPrimary) 0.9f else 0.45f
    val borderWidth = if (isPrimary) 1.2.dp else 0.7.dp
    val statusText = if (zone.status == "WEAKENED") "AUS" else zone.status.ifBlank { "ACTIVE" }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(baseColor.copy(alpha = if (isPrimary) 0.08f else 0.03f))
            .border(BorderStroke(borderWidth, baseColor.copy(alpha = alphaBorder)), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Left: Tag + Lot + Score
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Zone Tag Pill
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(baseColor.copy(alpha = 0.2f))
                        .border(BorderStroke(0.8.dp, baseColor), RoundedCornerShape(4.dp))
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = label,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = baseColor
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    Text(
                        text = "${zone.totalLot.toInt()}L | ${zone.strength} ${zone.score}",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = TextPrimary
                    )
                    Text(
                        text = "$${Formatters.formatPrice(zone.lo)} - $${Formatters.formatPrice(zone.hi)}",
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        color = TextMuted
                    )
                }
            }

            // Right: Status + Retest + Absorption
            Column(horizontalAlignment = Alignment.End) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = statusText,
                        fontSize = 9.5.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = if (statusText == "AUS") NeonAmber else baseColor
                    )
                    if (zone.absorptionHits > 0) {
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "⚡${zone.absorptionHits}x",
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            color = NeonAmber
                        )
                    }
                }
                Text(
                    text = "diuji ${zone.retestCount}x",
                    fontSize = 8.5.sp,
                    fontFamily = FontFamily.Monospace,
                    color = TextSecondary
                )
            }
        }
    }
}

@Composable
private fun LivePriceLaserBeam(
    price: Double,
    distToS1: Double?,
    distToD1: Double?,
    isCompression: Boolean
) {
    val beamColor = if (isCompression) NeonAmber else NeonCyan

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(beamColor.copy(alpha = 0.15f))
            .border(BorderStroke(1.2.dp, beamColor), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 5.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "⚡ LIVE PRICE",
                    fontSize = 9.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = beamColor
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = if (price > 0) "$${Formatters.formatPrice(price)}" else "-",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.Monospace,
                    color = TextPrimary
                )
            }

            // Distances
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                if (distToS1 != null) {
                    Text(
                        text = "▲ S1: +$${Formatters.formatPrice(distToS1)}",
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = NeonRed
                    )
                }
                if (distToD1 != null) {
                    Text(
                        text = "▼ D1: -$${Formatters.formatPrice(distToD1)}",
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = NeonGreen
                    )
                }
            }
        }
    }
}

@Composable
private fun MomentumBreakPipelineCard(breakStatus: SdBreak) {
    val steps = listOf("TEST", "WICK", "CLOSE", "MOMENTUM", "CONFIRMED")
    val supplyState = breakStatus.supplyState
    val demandState = breakStatus.demandState

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(BgCardElevated)
            .border(BorderStroke(0.7.dp, BorderSubtle), RoundedCornerShape(6.dp))
            .padding(8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "MOMENTUM BREAK PIPELINE",
                fontSize = 9.5.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = TextSecondary
            )
            Text(
                text = breakStatus.statusText.ifBlank { breakStatus.marketRead },
                fontSize = 9.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = if (breakStatus.noTradeZone) NeonAmber else NeonCyan
            )
        }

        Spacer(modifier = Modifier.height(6.dp))

        // Supply State Pipeline
        PipelineTrack(
            label = "SUPPLY BREAK",
            state = supplyState,
            isSupply = true,
            steps = steps
        )

        Spacer(modifier = Modifier.height(4.dp))

        // Demand State Pipeline
        PipelineTrack(
            label = "DEMAND BREAK",
            state = demandState,
            isSupply = false,
            steps = steps
        )
    }
}

@Composable
private fun PipelineTrack(
    label: String,
    state: String,
    isSupply: Boolean,
    steps: List<String>
) {
    val activeIndex = when {
        state.contains("CONFIRMED") -> 4
        state.contains("MOMENTUM") || state.contains("FOLLOW") -> 3
        state.contains("CLOSE") -> 2
        state.contains("WICK") -> 1
        state.contains("TEST") -> 0
        else -> -1
    }

    val glowColor = when {
        activeIndex == 4 -> if (isSupply) NeonGreen else NeonRed // Confirmed
        activeIndex in 1..3 -> NeonAmber // In-progress
        else -> TextMuted
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "$label: ${state.ifBlank { "NONE" }.replace("_", " ")}",
            fontSize = 9.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace,
            color = glowColor
        )

        Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
            steps.forEachIndexed { index, step ->
                val isReached = index <= activeIndex
                val isCurrent = index == activeIndex
                val pillColor = if (isCurrent) glowColor else if (isReached) glowColor.copy(alpha = 0.4f) else BorderSubtle

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(2.dp))
                        .background(if (isCurrent) pillColor.copy(alpha = 0.25f) else Color.Transparent)
                        .border(BorderStroke(0.6.dp, pillColor), RoundedCornerShape(2.dp))
                        .padding(horizontal = 3.dp, vertical = 1.dp)
                ) {
                    Text(
                        text = step,
                        fontSize = 7.5.sp,
                        fontWeight = if (isCurrent) FontWeight.Black else FontWeight.Normal,
                        fontFamily = FontFamily.Monospace,
                        color = if (isCurrent) pillColor else TextMuted
                    )
                }
            }
        }
    }
}

@Composable
private fun OrderFlowCombatFeed(
    decision: SdDecision,
    breakStatus: SdBreak,
    s1: SdZone?,
    d1: SdZone?
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(BgCyberDark)
            .border(BorderStroke(0.8.dp, BorderSubtle), RoundedCornerShape(6.dp))
            .padding(8.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "📡 ORDER-FLOW TELEMETRY FEED",
                    fontSize = 8.5.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    color = NeonCyan
                )
                Text(
                    text = "LIVE",
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace,
                    color = NeonGreen
                )
            }
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = "▶ RADAR: ${decision.location} (${decision.marketState})",
                fontSize = 8.5.sp,
                fontFamily = FontFamily.Monospace,
                color = TextSecondary
            )
            Text(
                text = "▶ EROSION: S1 ABSORB=${s1?.absorptionHits ?: 0}x | D1 ABSORB=${d1?.absorptionHits ?: 0}x",
                fontSize = 8.5.sp,
                fontFamily = FontFamily.Monospace,
                color = if ((s1?.absorptionHits ?: 0) > 0 || (d1?.absorptionHits ?: 0) > 0) NeonAmber else TextMuted
            )
            Text(
                text = "▶ MOMENTUM READ: ${breakStatus.marketRead} | DIR: ${breakStatus.direction}",
                fontSize = 8.5.sp,
                fontFamily = FontFamily.Monospace,
                color = TextSecondary
            )
        }
    }
}
