package com.dadang.chainreaction.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Timeline
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.data.model.LocationInfo
import com.dadang.chainreaction.data.model.UsdInfo
import com.dadang.chainreaction.ui.theme.BgCardElevated
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
fun MarketOverviewCard(
    location: LocationInfo,
    usd: UsdInfo,
    modifier: Modifier = Modifier
) {
    var isExpanded by remember { mutableStateOf(false) }

    CyberCard(
        modifier = modifier.clickable { isExpanded = !isExpanded },
        borderColor = NeonCyan.copy(alpha = 0.3f)
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Timeline,
                        contentDescription = null,
                        tint = NeonCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "MARKET OVERVIEW & VALUE AREA",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = NeonCyan,
                        letterSpacing = 0.8.sp
                    )
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    DirectionPill(
                        direction = location.position,
                        fontSize = 9.sp
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Icon(
                        imageVector = if (isExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                        contentDescription = "Expand",
                        tint = TextSecondary,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Primary Summary Grid
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "POC Level",
                    value = Formatters.formatPrice(location.poc),
                    subValue = "Dist: ${location.distanceToPoc}",
                    valueColor = GoldAccent,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "VA Range",
                    value = "${Formatters.formatPrice(location.valPrice)} - ${Formatters.formatPrice(location.vahPrice)}",
                    subValue = "Bias: ${location.vaBias}",
                    valueColor = NeonCyan,
                    modifier = Modifier.weight(1.3f)
                )
            }

            // Expanded Details Section
            AnimatedVisibility(visible = isExpanded) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 10.dp)
                ) {
                    // Value Area Visual Representation
                    ValueAreaVisualBar(
                        currentPrice = location.currentPrice,
                        valPrice = location.valPrice,
                        pocPrice = location.poc,
                        vahPrice = location.vahPrice
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    // Secondary Metrics (ATR, Range Distance, DXY)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        MetricBox(
                            label = "ATR (14)",
                            value = "${location.atr14}",
                            subValue = "Volatilitas",
                            modifier = Modifier.weight(1f)
                        )
                        MetricBox(
                            label = "Range 24H Dist",
                            value = "${location.range24h}",
                            subValue = "Jarak Poin",
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // DXY Macro Context Box (Categorical data only, no fabricated prices)
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
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "USD MACRO: ${usd.symbol}",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace,
                                    color = TextPrimary
                                )
                                DirectionPill(direction = "${usd.dir} (${usd.bias})", fontSize = 9.sp)
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "Efek ke Emas: ${usd.goldEffect}",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = if (usd.goldEffect.contains("TURUN")) NeonRed else NeonGreen
                            )
                            if (usd.nextEvent.isNotBlank() && usd.nextEvent != "-") {
                                Text(
                                    text = "Next: ${usd.nextEvent} (${Formatters.formatMinsUntil(usd.nextMins)})",
                                    fontSize = 10.sp,
                                    color = TextSecondary
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ValueAreaVisualBar(
    currentPrice: Double,
    valPrice: Double,
    pocPrice: Double,
    vahPrice: Double
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(BgCardElevated)
            .padding(horizontal = 10.dp, vertical = 8.dp)
    ) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(text = "VAL: ${Formatters.formatPrice(valPrice)}", fontSize = 9.sp, color = NeonCyan)
                Text(text = "POC: ${Formatters.formatPrice(pocPrice)}", fontSize = 9.sp, color = GoldAccent, fontWeight = FontWeight.Bold)
                Text(text = "VAH: ${Formatters.formatPrice(vahPrice)}", fontSize = 9.sp, color = NeonCyan)
            }
            Spacer(modifier = Modifier.height(4.dp))
            // Progress Bar simulation
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(6.dp)
                    .clip(RoundedCornerShape(3.dp))
                    .background(Color(0xFF1E293B))
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.7f)
                        .height(6.dp)
                        .background(NeonCyan.copy(alpha = 0.4f))
                )
            }
        }
    }
}
