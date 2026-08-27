package com.dadang.chainreaction.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonGreenBg
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.NeonRedBg
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.Formatters
import kotlinx.coroutines.delay

@Composable
fun LivePriceHeader(
    symbol: String,
    price: Double,
    balance: Double,
    equity: Double,
    priceDeltaDirection: Int,
    modifier: Modifier = Modifier
) {
    var flashColor by remember { mutableStateOf(Color.Transparent) }

    LaunchedEffect(price) {
        if (priceDeltaDirection > 0) {
            flashColor = NeonGreenBg
            delay(500)
            flashColor = Color.Transparent
        } else if (priceDeltaDirection < 0) {
            flashColor = NeonRedBg
            delay(500)
            flashColor = Color.Transparent
        }
    }

    val animatedBg by animateColorAsState(
        targetValue = flashColor,
        animationSpec = tween(durationMillis = 300),
        label = "price_flash"
    )

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(if (animatedBg == Color.Transparent) BgCardElevated else animatedBg)
            .border(1.dp, BorderSubtle, RoundedCornerShape(12.dp))
            .padding(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(GoldAccent)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = symbol.uppercase(),
                        fontWeight = FontWeight.Black,
                        fontSize = 14.sp,
                        fontFamily = FontFamily.Monospace,
                        color = GoldAccent,
                        letterSpacing = 1.sp
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "GOLD SPOT",
                        fontSize = 10.sp,
                        color = TextMuted
                    )
                }
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = "$" + Formatters.formatPrice(price),
                    fontSize = 28.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = when (priceDeltaDirection) {
                        1 -> NeonGreen
                        -1 -> NeonRed
                        else -> TextPrimary
                    },
                    letterSpacing = (-0.5).sp
                )
            }

            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "ACCOUNT STATUS",
                    fontSize = 9.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = TextMuted,
                    letterSpacing = 0.5.sp
                )
                Spacer(modifier = Modifier.height(2.dp))
                Row {
                    Text(
                        text = "BAL: ",
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        color = TextSecondary
                    )
                    Text(
                        text = Formatters.formatCurrency(balance),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = TextPrimary
                    )
                }
                Row {
                    Text(
                        text = "EQT: ",
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        color = TextSecondary
                    )
                    Text(
                        text = Formatters.formatCurrency(equity),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = if (equity >= balance) NeonGreen else NeonRed
                    )
                }
            }
        }
    }
}
