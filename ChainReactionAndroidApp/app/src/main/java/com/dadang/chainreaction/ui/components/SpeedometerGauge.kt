package com.dadang.chainreaction.ui.components

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
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
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
import kotlin.math.cos
import kotlin.math.sin

/**
 * Ultra-Smooth High-Tech Cyberpunk Radial Speedometer Gauge
 * Animasi jarum analog halus dengan CubicBezier interpolation.
 */
@Composable
fun SpeedometerGauge(
    value: Float, // Multiplier (e.g. 3.8x)
    maxValue: Float = 5.0f,
    unit: String = "x",
    label: String = "BREAKOUT VELOCITY GAUGE",
    direction: String = "BUY", // BUY, SELL, NEUTRAL
    statusText: String = "STRONG ACCELERATION",
    modifier: Modifier = Modifier
) {
    val clampedValue = value.coerceIn(0f, maxValue)
    val fraction = clampedValue / maxValue

    // Smooth gliding needle animation (700ms cubic bezier easing - tanpa getar/flicker)
    val animatedFraction by animateFloatAsState(
        targetValue = fraction,
        animationSpec = tween(
            durationMillis = 700,
            easing = CubicBezierEasing(0.25f, 0.1f, 0.25f, 1.0f)
        ),
        label = "smooth_speedometer_needle"
    )

    val isBuy = direction.contains("BUY", ignoreCase = true)
    val isSell = direction.contains("SELL", ignoreCase = true)
    val accentColor = if (isBuy) NeonGreen else if (isSell) NeonRed else GoldAccent

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(BgCardElevated)
            .border(1.dp, BorderSubtle, RoundedCornerShape(12.dp))
            .padding(12.dp)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Header Top
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Speed,
                        contentDescription = null,
                        tint = GoldAccent,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = label,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = GoldAccent,
                        letterSpacing = 1.sp
                    )
                }

                DirectionPill(
                    direction = "$direction (${String.format("%.1f", value)}$unit)",
                    fontSize = 9.5.sp
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            // Radial Speedometer Canvas
            Box(
                modifier = Modifier
                    .width(240.dp)
                    .height(125.dp),
                contentAlignment = Alignment.BottomCenter
            ) {
                Canvas(
                    modifier = Modifier
                        .width(240.dp)
                        .height(240.dp)
                ) {
                    drawSpeedometerArc(
                        fraction = animatedFraction,
                        accentColor = accentColor
                    )
                }

                // Digital Center Readout
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(bottom = 6.dp)
                ) {
                    Text(
                        text = String.format("%.1f", value) + unit,
                        fontSize = 28.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace,
                        color = accentColor,
                        letterSpacing = (-0.5).sp
                    )
                    Text(
                        text = statusText.uppercase(),
                        fontSize = 9.5.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = TextSecondary,
                        letterSpacing = 0.5.sp
                    )
                }
            }

            // Bottom Gauge Range Markers
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 2.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(text = "0.0$unit (IDLE)", fontSize = 8.5.sp, fontFamily = FontFamily.Monospace, color = TextMuted)
                Text(text = "${maxValue / 2}$unit (MED)", fontSize = 8.5.sp, fontFamily = FontFamily.Monospace, color = TextMuted)
                Text(text = "$maxValue$unit (MAX)", fontSize = 8.5.sp, fontFamily = FontFamily.Monospace, color = accentColor)
            }
        }
    }
}

private fun DrawScope.drawSpeedometerArc(
    fraction: Float,
    accentColor: Color
) {
    val strokeWidth = 14.dp.toPx()
    val padding = 16.dp.toPx()
    val arcSize = Size(size.width - padding * 2, size.height - padding * 2)
    val topLeft = Offset(padding, padding)

    // 1. Background Arc (180 degrees, from 180° to 360°)
    drawArc(
        color = Color(0xFF131D2E),
        startAngle = 180f,
        sweepAngle = 180f,
        useCenter = false,
        topLeft = topLeft,
        size = arcSize,
        style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
    )

    // 2. Active Gradient Arc
    val activeSweepAngle = (180f * fraction).coerceIn(2f, 180f)
    val gradientBrush = Brush.sweepGradient(
        0.0f to NeonCyan,
        0.5f to NeonAmber,
        1.0f to accentColor,
        center = Offset(size.width / 2, size.height / 2)
    )

    drawArc(
        brush = gradientBrush,
        startAngle = 180f,
        sweepAngle = activeSweepAngle,
        useCenter = false,
        topLeft = topLeft,
        size = arcSize,
        style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
    )

    // 3. Tick Marks
    val centerX = size.width / 2
    val centerY = size.height / 2
    val radius = (size.width - padding * 2) / 2

    for (i in 0..10) {
        val angleDeg = 180f + (i * 18f)
        val angleRad = Math.toRadians(angleDeg.toDouble())
        val isMajor = i % 2 == 0
        val tickLength = if (isMajor) 8.dp.toPx() else 4.dp.toPx()

        val startX = centerX + (radius - strokeWidth / 2 - 4.dp.toPx()) * cos(angleRad).toFloat()
        val startY = centerY + (radius - strokeWidth / 2 - 4.dp.toPx()) * sin(angleRad).toFloat()

        val endX = centerX + (radius - strokeWidth / 2 - 4.dp.toPx() - tickLength) * cos(angleRad).toFloat()
        val endY = centerY + (radius - strokeWidth / 2 - 4.dp.toPx() - tickLength) * sin(angleRad).toFloat()

        drawLine(
            color = if (isMajor) NeonCyan.copy(alpha = 0.6f) else BorderSubtle,
            start = Offset(startX, startY),
            end = Offset(endX, endY),
            strokeWidth = if (isMajor) 2.dp.toPx() else 1.dp.toPx()
        )
    }

    // 4. Center Hub & Smooth Needle Pointer
    val needleAngle = 180f + (180f * fraction)
    val needleRad = Math.toRadians(needleAngle.toDouble())
    val needleLength = radius - strokeWidth - 6.dp.toPx()

    val needleTipX = centerX + needleLength * cos(needleRad).toFloat()
    val needleTipY = centerY + needleLength * sin(needleRad).toFloat()

    // Smooth Needle Line
    drawLine(
        color = accentColor,
        start = Offset(centerX, centerY),
        end = Offset(needleTipX, needleTipY),
        strokeWidth = 3.dp.toPx(),
        cap = StrokeCap.Round
    )

    // Center Outer Ring & Inner Hub
    drawCircle(
        color = BgCyberDark,
        radius = 12.dp.toPx(),
        center = Offset(centerX, centerY)
    )
    drawCircle(
        color = accentColor,
        radius = 6.dp.toPx(),
        center = Offset(centerX, centerY)
    )
}
