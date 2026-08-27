package com.dadang.chainreaction.ui.screens.command

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ElectricBolt
import androidx.compose.material.icons.filled.Hub
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
import com.dadang.chainreaction.data.model.MomentumSignal
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.ui.components.CountdownBar
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BgCyberDark
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonAmber
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

@Composable
fun CommanderHudScreen(
    status: SultanStatus?,
    priceDeltaDirection: Int,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    if (status == null) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(BgCyberDark),
            contentAlignment = Alignment.Center
        ) {
            Text("Memuat data HUD...", color = TextSecondary)
        }
        return
    }

    val action = status.context.action
    val isBuy = action.contains("BUY")
    val isSell = action.contains("SELL")
    val actionColor = when {
        isBuy -> NeonGreen
        isSell -> NeonRed
        else -> NeonAmber
    }

    val chain = status.signals.chainSignal
    val isLayerBuy = chain?.dir?.contains("BUY") == true
    val isLayerSell = chain?.dir?.contains("SELL") == true
    val chainColor = if (isLayerBuy) NeonGreen else if (isLayerSell) NeonRed else GoldAccent

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BgCyberDark)
            .padding(14.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // 1. Top Bar HUD with Identity & Exit Button
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(NeonGreen)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    Text(
                        text = "COMMANDER DADANG WAHYUONO",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = GoldAccent,
                        letterSpacing = 1.sp
                    )
                    Text(
                        text = "CHAIN REACTION HUD TERMINAL",
                        fontSize = 8.5.sp,
                        fontFamily = FontFamily.Monospace,
                        color = NeonCyan
                    )
                }
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(BgCardElevated)
                    .border(BorderStroke(1.dp, BorderSubtle), RoundedCornerShape(8.dp))
                    .clickable { onClose() }
                    .padding(horizontal = 10.dp, vertical = 6.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Exit HUD",
                        tint = TextPrimary,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "EXIT",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = TextPrimary
                    )
                }
            }
        }

        // 2. Center Hero: Huge Price & Action
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "XAUUSD GOLD SPOT",
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
                letterSpacing = 2.sp
            )

            Spacer(modifier = Modifier.height(2.dp))

            Text(
                text = "$" + Formatters.formatPrice(status.price),
                fontSize = 42.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                color = when (priceDeltaDirection) {
                    1 -> NeonGreen
                    -1 -> NeonRed
                    else -> TextPrimary
                },
                letterSpacing = (-1).sp
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Massive Action Badge
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(10.dp))
                    .background(actionColor.copy(alpha = 0.15f))
                    .border(BorderStroke(2.dp, actionColor), RoundedCornerShape(10.dp))
                    .padding(horizontal = 20.dp, vertical = 8.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.ElectricBolt,
                        contentDescription = null,
                        tint = actionColor,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = action.replace("_", " "),
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = actionColor,
                        letterSpacing = 1.sp
                    )
                }
            }
        }

        // 3. ⭐ MOMENTUM TRIAD & CHAIN LAYER HERO IN HUD ⭐
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .background(BgCardElevated)
                .border(BorderStroke(1.2.dp, chainColor.copy(alpha = 0.5f)), RoundedCornerShape(8.dp))
                .padding(10.dp)
        ) {
            Column {
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
                            modifier = Modifier.size(15.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "LIVE BREAKOUT MOMENTUM",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            color = GoldAccent
                        )
                    }

                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(if (isLayerBuy) NeonGreenBg else if (isLayerSell) NeonRedBg else NeonCyanBg)
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = "LAYER ${chain?.layer ?: 0} (${chain?.dir ?: "-"})",
                            fontSize = 9.5.sp,
                            fontWeight = FontWeight.Black,
                            fontFamily = FontFamily.Monospace,
                            color = chainColor
                        )
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    HudMomentumPill(
                        label = "M5 CORE",
                        signal = status.signals.momentumM5,
                        modifier = Modifier.weight(1f)
                    )
                    HudMomentumPill(
                        label = "BOOKMAP",
                        signal = status.signals.momentumM5Bookmap,
                        modifier = Modifier.weight(1f)
                    )
                    HudMomentumPill(
                        label = "FOOTPRINT",
                        signal = status.signals.momentumM5Footprint,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }

        // 4. Secondary Grid: Score, CVD, Alignment, Nearest Wall
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                HudMetricTile(
                    label = "CONVICTION",
                    value = "${status.conviction.score}/${status.conviction.max}",
                    subText = status.conviction.grade,
                    valueColor = if (status.conviction.score >= 4) NeonGreen else NeonAmber,
                    modifier = Modifier.weight(1f)
                )
                HudMetricTile(
                    label = "ALIGNMENT",
                    value = Formatters.formatPercent(status.regime.alignmentPct),
                    subText = status.regime.htfBias,
                    valueColor = NeonCyan,
                    modifier = Modifier.weight(1f)
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                HudMetricTile(
                    label = "CVD FLOW",
                    value = "${status.flow.cvd}",
                    subText = status.flow.flowDominant,
                    valueColor = if (status.flow.cvd >= 0) NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                HudMetricTile(
                    label = "NEAREST WALL",
                    value = "${status.liquidity.nearestWallSide} (${status.liquidity.nearestWallDistance}p)",
                    subText = "Imb: ${status.liquidity.wallImbalance}",
                    valueColor = if (status.liquidity.nearestWallSide == "BID") NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
            }
        }

        // 5. Bottom Countdowns
        Column {
            Text(
                text = "CANDLE TIMERS",
                fontSize = 8.5.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                color = TextMuted,
                letterSpacing = 0.5.sp,
                modifier = Modifier.padding(bottom = 3.dp)
            )
            CountdownBar(countdown = status.signals.countdown)
        }
    }
}

@Composable
private fun HudMomentumPill(
    label: String,
    signal: MomentumSignal?,
    modifier: Modifier = Modifier
) {
    val dir = signal?.dir?.trim()?.uppercase() ?: ""
    val isBuy = dir == "BUY"
    val isSell = dir == "SELL"
    val isStrong = signal?.text?.contains("STRONG", ignoreCase = true) == true

    val (bg, border, textCol) = when {
        isBuy -> Triple(NeonGreenBg, if (isStrong) NeonGreen else NeonGreenBorder, NeonGreen)
        isSell -> Triple(NeonRedBg, if (isStrong) NeonRed else NeonRedBorder, NeonRed)
        else -> Triple(BgCyberDark, BorderSubtle, TextMuted)
    }

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(bg)
            .border(BorderStroke(1.dp, border), RoundedCornerShape(6.dp))
            .padding(horizontal = 4.dp, vertical = 6.dp)
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = label,
                fontSize = 7.5.sp,
                fontFamily = FontFamily.Monospace,
                color = TextSecondary
            )
            Spacer(modifier = Modifier.height(1.dp))
            Text(
                text = signal?.text?.ifBlank { "-" } ?: "-",
                fontSize = 9.5.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                color = textCol,
                maxLines = 1
            )
        }
    }
}

@Composable
private fun HudMetricTile(
    label: String,
    value: String,
    subText: String,
    valueColor: Color,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(BgCardElevated)
            .border(BorderStroke(1.dp, BorderSubtle), RoundedCornerShape(8.dp))
            .padding(10.dp)
    ) {
        Column {
            Text(
                text = label,
                fontSize = 8.5.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = TextMuted
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = value,
                fontSize = 16.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                color = valueColor
            )
            Text(
                text = subText,
                fontSize = 10.sp,
                color = TextSecondary,
                maxLines = 1
            )
        }
    }
}
