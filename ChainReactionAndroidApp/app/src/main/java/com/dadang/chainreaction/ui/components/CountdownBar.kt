package com.dadang.chainreaction.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.data.model.CountdownInfo
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.util.Formatters

@Composable
fun CountdownBar(
    countdown: CountdownInfo,
    modifier: Modifier = Modifier
) {
    val items = listOf(
        Pair("M1", countdown.m1),
        Pair("M5", countdown.m5),
        Pair("M15", countdown.m15),
        Pair("M30", countdown.m30),
        Pair("H1", countdown.h1),
        Pair("H4", countdown.h4)
    )

    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        items.forEach { (tf, seconds) ->
            CountdownPill(
                timeframe = tf,
                seconds = seconds,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun CountdownPill(
    timeframe: String,
    seconds: Long,
    modifier: Modifier = Modifier
) {
    val isUrgent = seconds in 1..60

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(BgCardElevated)
            .border(
                1.dp,
                if (isUrgent) NeonAmber.copy(alpha = 0.6f) else BorderSubtle,
                RoundedCornerShape(6.dp)
            )
            .padding(vertical = 4.dp, horizontal = 2.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = timeframe,
                fontSize = 9.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = if (isUrgent) NeonAmber else NeonCyan
            )
            Text(
                text = Formatters.formatCountdownSeconds(seconds),
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.SemiBold,
                color = if (isUrgent) NeonAmber else TextPrimary
            )
        }
    }
}
