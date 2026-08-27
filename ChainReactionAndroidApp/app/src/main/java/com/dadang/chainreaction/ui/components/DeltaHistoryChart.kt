package com.dadang.chainreaction.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import kotlin.math.abs
import kotlin.math.max

/**
 * Visual Canvas Bar Chart untuk Delta History (Order-Flow Delta Pulse per-tick/candle)
 */
@Composable
fun DeltaHistoryChart(
    deltaHistory: List<Double>,
    currentDelta: Double,
    modifier: Modifier = Modifier
) {
    val history = if (deltaHistory.isEmpty()) listOf(0.0) else deltaHistory
    val maxAbsDelta = history.maxOfOrNull { abs(it) }?.coerceAtLeast(20.0) ?: 50.0

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(BgCardElevated)
            .border(0.8.dp, BorderSubtle, RoundedCornerShape(8.dp))
            .padding(10.dp)
    ) {
        Column {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.BarChart,
                        contentDescription = null,
                        tint = NeonCyan,
                        modifier = Modifier.size(15.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "ORDER FLOW DELTA HISTOGRAM",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = NeonCyan,
                        letterSpacing = 0.5.sp
                    )
                }

                Text(
                    text = "LAST: ${if (currentDelta > 0) "+" else ""}${currentDelta.toInt()}",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.Monospace,
                    color = if (currentDelta >= 0) NeonGreen else NeonRed
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Canvas Bar Chart
            Canvas(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
            ) {
                val width = size.width
                val height = size.height
                val midY = height / 2f
                val barCount = history.size
                val spacing = 2.dp.toPx()
                val totalSpacing = spacing * (barCount - 1)
                val barWidth = ((width - totalSpacing) / barCount).coerceAtLeast(3f)

                // 1. Zero Center Line
                drawLine(
                    color = Color(0xFF2A3C59),
                    start = Offset(0f, midY),
                    end = Offset(width, midY),
                    strokeWidth = 1.dp.toPx()
                )

                // 2. Draw Vertical Delta Bars
                history.forEachIndexed { index, delta ->
                    val x = index * (barWidth + spacing)
                    val fraction = (abs(delta) / maxAbsDelta).toFloat().coerceIn(0.04f, 1f)
                    val barHeight = (midY - 4.dp.toPx()) * fraction

                    val isBuy = delta >= 0
                    val barColor = if (isBuy) NeonGreen else NeonRed
                    val isLast = index == history.lastIndex

                    val top = if (isBuy) midY - barHeight else midY
                    val barActualHeight = barHeight.coerceAtLeast(2.dp.toPx())

                    drawRect(
                        color = if (isLast) barColor else barColor.copy(alpha = 0.75f),
                        topLeft = Offset(x, top),
                        size = Size(barWidth, barActualHeight)
                    )

                    // Draw glow on the last active bar
                    if (isLast) {
                        drawCircle(
                            color = barColor,
                            radius = 2.5.dp.toPx(),
                            center = Offset(x + barWidth / 2, if (isBuy) top else top + barActualHeight)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(4.dp))

            // Axis labels
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "◀ 30 TICKS AGO",
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace,
                    color = TextMuted
                )
                Text(
                    text = "+${maxAbsDelta.toInt()} / -${maxAbsDelta.toInt()}",
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace,
                    color = TextMuted
                )
                Text(
                    text = "NOW (LIVE) ▶",
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace,
                    color = NeonCyan
                )
            }
        }
    }
}
