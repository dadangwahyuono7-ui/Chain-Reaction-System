package com.dadang.chainreaction.ui.screens.bookmap

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
import androidx.compose.material.icons.filled.ElectricBolt
import androidx.compose.material.icons.filled.Layers
import androidx.compose.material.icons.filled.Visibility
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
import com.dadang.chainreaction.data.model.BookmapReadInfo
import com.dadang.chainreaction.data.model.LiquidityInfo
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.data.model.WallSweepInfo
import com.dadang.chainreaction.ui.components.CyberCard
import com.dadang.chainreaction.ui.components.DirectionPill
import com.dadang.chainreaction.ui.components.LiquidityLadderView
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
fun BookmapScreen(
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
        // 1. Bookmap Read Verdict Card
        BookmapReadCard(bookmapRead = status.bookmapRead)

        // 2. Wall Sweep Live Alert Banner
        WallSweepBanner(sweep = status.wallSweep)

        // 3. Liquidity Imbalance & Total Lot Summary
        LiquidityImbalanceCard(liq = status.liquidity)

        // 4. Bid & Ask Liquidity Order Book Ladder
        CyberCard {
            Column(modifier = Modifier.fillMaxWidth()) {
                SectionHeader(
                    title = "ORDER BOOK DEPTH LADDER",
                    icon = Icons.Default.Layers,
                    badgeText = "CURRENT: $${Formatters.formatPrice(status.price)}",
                    badgeColor = GoldAccent
                )
                LiquidityLadderView(
                    bidLadder = status.liquidity.bidLadder,
                    askLadder = status.liquidity.askLadder,
                    currentPrice = status.price
                )
            }
        }

        Spacer(modifier = Modifier.height(80.dp))
    }
}

@Composable
private fun BookmapReadCard(bookmapRead: BookmapReadInfo) {
    CyberCard(
        borderColor = NeonCyan.copy(alpha = 0.4f)
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Visibility,
                        contentDescription = null,
                        tint = NeonCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "BOOKMAP ORDER-FLOW READ",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = NeonCyan,
                        letterSpacing = 0.8.sp
                    )
                }
                DirectionPill(direction = "VERDICT: ${bookmapRead.verdict}", fontSize = 9.sp)
            }

            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "Wall Ratio",
                    value = bookmapRead.wall,
                    valueColor = NeonCyan,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "CVD",
                    value = bookmapRead.cvd,
                    valueColor = if (bookmapRead.cvd.startsWith("+")) NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Iceberg",
                    value = bookmapRead.iceberg,
                    valueColor = if (bookmapRead.iceberg != "-") GoldAccent else TextMuted,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Absorption",
                    value = bookmapRead.absorption,
                    valueColor = if (bookmapRead.absorption != "-") NeonAmber else TextMuted,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun WallSweepBanner(sweep: WallSweepInfo) {
    if (!sweep.active) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .background(BgCardElevated)
                .border(BorderStroke(0.8.dp, BorderSubtle), RoundedCornerShape(8.dp))
                .padding(horizontal = 10.dp, vertical = 6.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "WALL SWEEP STATUS: INACTIVE",
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    color = TextMuted
                )
                Text(
                    text = "Normal Order Flow",
                    fontSize = 10.sp,
                    color = TextSecondary
                )
            }
        }
        return
    }

    // Active Sweep Alert
    CyberCard(
        backgroundColor = NeonAmber.copy(alpha = 0.15f),
        borderColor = NeonAmber,
        borderWidth = 1.5f
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
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    Text(
                        text = "⚠️ ACTIVE WALL SWEEP: ${sweep.side}",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = NeonAmber
                    )
                    Text(
                        text = "@ $${Formatters.formatPrice(sweep.price)} • Size: ${Formatters.formatLot(sweep.size)}L (${sweep.sinceSec}s ago)",
                        fontSize = 11.sp,
                        color = TextPrimary
                    )
                }
            }
            DirectionPill(direction = sweep.status, fontSize = 9.sp)
        }
    }
}

@Composable
private fun LiquidityImbalanceCard(liq: LiquidityInfo) {
    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "LIQUIDITY TOTALS & IMBALANCE",
                badgeText = "IMB: ${liq.wallImbalance}",
                badgeColor = if (liq.wallImbalance > 0) NeonGreen else NeonRed
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "Total Bid Lot",
                    value = "${liq.bidWallTotalLot} L",
                    subValue = "${liq.bidWallCount} walls",
                    valueColor = NeonGreen,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Total Ask Lot",
                    value = "${liq.askWallTotalLot} L",
                    subValue = "${liq.askWallCount} walls",
                    valueColor = NeonRed,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Imbalance Visual Meter Bar
            Text(
                text = "BID / ASK RATIO PROPORTION",
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                color = TextMuted
            )
            Spacer(modifier = Modifier.height(4.dp))

            val total = (liq.bidWallTotalLot + liq.askWallTotalLot).coerceAtLeast(1.0)
            val bidFraction = (liq.bidWallTotalLot / total).toFloat().coerceIn(0.05f, 0.95f)

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(RoundedCornerShape(4.dp))
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(bidFraction)
                        .height(8.dp)
                        .background(NeonGreen)
                )
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .background(NeonRed)
                )
            }
        }
    }
}
