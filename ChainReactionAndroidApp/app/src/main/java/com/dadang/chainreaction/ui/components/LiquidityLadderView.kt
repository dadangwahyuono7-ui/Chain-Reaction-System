package com.dadang.chainreaction.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
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
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.Formatters

@Composable
fun LiquidityLadderView(
    bidLadder: List<List<Double>>,
    askLadder: List<List<Double>>,
    currentPrice: Double,
    modifier: Modifier = Modifier
) {
    val maxLot = (bidLadder + askLadder)
        .mapNotNull { if (it.size >= 2) it[1] else null }
        .maxOrNull()?.coerceAtLeast(1.0) ?: 30.0

    Column(modifier = modifier.fillMaxWidth()) {
        // Table Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 6.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = "BID DEPTH (SUPPORT)",
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = NeonGreen
            )
            Text(
                text = "ASK DEPTH (RESISTANCE)",
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = NeonRed
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Bid Ladder Column
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp)
            ) {
                if (bidLadder.isEmpty()) {
                    Text(
                        text = "Tidak ada bid wall",
                        fontSize = 11.sp,
                        color = TextMuted,
                        modifier = Modifier.padding(vertical = 4.dp)
                    )
                } else {
                    bidLadder.take(6).forEach { row ->
                        if (row.size >= 2) {
                            LadderRowItem(
                                price = row[0],
                                lot = row[1],
                                maxLot = maxLot,
                                isBid = true,
                                currentPrice = currentPrice
                            )
                        }
                    }
                }
            }

            // Ask Ladder Column
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp)
            ) {
                if (askLadder.isEmpty()) {
                    Text(
                        text = "Tidak ada ask wall",
                        fontSize = 11.sp,
                        color = TextMuted,
                        modifier = Modifier.padding(vertical = 4.dp)
                    )
                } else {
                    askLadder.take(6).forEach { row ->
                        if (row.size >= 2) {
                            LadderRowItem(
                                price = row[0],
                                lot = row[1],
                                maxLot = maxLot,
                                isBid = false,
                                currentPrice = currentPrice
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun LadderRowItem(
    price: Double,
    lot: Double,
    maxLot: Double,
    isBid: Boolean,
    currentPrice: Double
) {
    val barColor = if (isBid) NeonGreen.copy(alpha = 0.25f) else NeonRed.copy(alpha = 0.25f)
    val textColor = if (isBid) NeonGreen else NeonRed
    val fraction = (lot / maxLot).toFloat().coerceIn(0.05f, 1f)

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(26.dp)
            .clip(RoundedCornerShape(4.dp))
            .background(BgCardElevated)
    ) {
        // Depth bar filling background
        Box(
            modifier = Modifier
                .fillMaxWidth(fraction)
                .height(26.dp)
                .align(if (isBid) Alignment.CenterEnd else Alignment.CenterStart)
                .background(barColor)
        )

        // Text Row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 6.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = Formatters.formatPrice(price),
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.SemiBold,
                color = textColor
            )
            Text(
                text = "${Formatters.formatLot(lot)} L",
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
        }
    }
}
